from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from filelock import FileLock, Timeout
from pydantic import BaseModel, ValidationError

from hx.adapters import CodexAdapter, FakeAdapter
from hx.config import canonical, digest, snapshot
from hx.failure_evidence import focused_output
from hx.git import assert_clean, check_scope, clone, derive, git, resolve_base, validate_candidate
from hx.models import (
    Cancelled,
    Candidate,
    Consolidated,
    GateError,
    Handoff,
    HXError,
    Review,
    Settings,
    StartupError,
    Task,
    Verification,
    WorkerSummary,
)
from hx.store import Store, atomic_write, now
from hx.verification import Verifier


def validate_review(review: Review, candidate: Candidate) -> None:
    if review.candidate_commit != candidate.candidate_commit:
        raise GateError("review references a different candidate revision")
    seen = set()
    root = Path(candidate.workspace).resolve()
    for finding in review.findings:
        if finding.id in seen:
            raise GateError("duplicate finding ID in review")
        seen.add(finding.id)
        file = root / finding.file
        if not file.resolve().is_relative_to(root) or not file.is_file():
            raise GateError(f"finding references a nonexistent file: {finding.file}")
        if finding.line > len(file.read_text("utf-8", errors="replace").splitlines()):
            raise GateError("finding references a nonexistent line")


def source_findings(reviews: dict[str, Review]) -> dict:
    return {
        f"{role}:{finding.id}": finding.model_dump()
        for role, review in reviews.items()
        for finding in review.findings
    }


def validate_consolidation(result: Consolidated, findings: dict, commit: str) -> None:
    if result.candidate_commit != commit:
        raise GateError("consolidation references a different revision")
    sources = [source for group in result.groups for source in group.sources]
    if len(sources) != len(set(sources)) or set(sources) != set(findings):
        raise GateError("consolidation must account for every source finding exactly once")


def derive_with_test_plan(repo: Path, task: Task, commit: str,
                          previous: Candidate | None, summary: WorkerSummary,
                          metadata_changed: bool = False) -> Candidate:
    """A revised test plan can preserve source; initial/no-op claims cannot."""
    commands = summary.verification_commands
    if (previous is not None and commands and (commands != previous.verification_commands or metadata_changed)
            and not git(repo, "status", "--porcelain")):
        if commit != previous.candidate_commit or git(repo, "remote"):
            raise GateError("test-plan revision changed history or configured a remote")
        result = previous.model_copy(update={"workspace": str(repo.resolve()),
            "input_commit": commit, "verification_commands": commands})
        validate_candidate(result, task)
        return result
    result = derive(repo, task.base_commit, commit, task)
    return result.model_copy(update={"verification_commands": commands})


class Engine:
    def __init__(self, store: Store, settings: Settings, adapter=None):
        self.store = store
        self.settings = settings
        self.adapter = adapter or (
            FakeAdapter() if settings.adapter == "fake" else CodexAdapter(settings)
        )
        self.config = snapshot(settings)
        self.verifier = Verifier(settings)

    def _clone(self, source: Path, destination: Path, commit: str) -> Path:
        return clone(source, destination, commit)

    def create(self, task: Task) -> dict:
        base = resolve_base(task)
        # Resolve HEAD now, not again after an external developer advances the source branch.
        task = task.model_copy(update={"base_commit": base})
        return self.store.create(task.model_dump(), self.config, base)

    def check_control(self, run_id: str, deadline: float) -> None:
        run = self.store.get(run_id)
        if run["cancel_requested"]:
            raise Cancelled("run cancelled by human")
        if time.monotonic() >= deadline:
            raise HXError("run time budget exhausted")
        if (self.settings.workflow != "single"
                and run["observed_tokens"] >= self.settings.max_observed_tokens):
            raise HXError("observed token budget exhausted (usage reported at turn boundaries)")

    def model_headroom(self, run_id: str) -> int:
        return self.settings.max_observed_tokens - self.store.get(run_id)["observed_tokens"]

    def execute(self, run_id: str, resume: bool = False) -> dict:
        lock = FileLock(str(self.store.run_dir(run_id) / "execution.lock"))
        try:
            with lock.acquire(timeout=0):
                return self._execute_locked(run_id, resume)
        except Timeout as exc:
            raise HXError("this run is already executing or being decided") from exc

    def _execute_locked(self, run_id: str, resume: bool) -> dict:
        run = self.store.get(run_id)
        if run["config"]["fingerprint"] != self.config["fingerprint"]:
            raise GateError(
                "runtime/configuration changed; create a new run instead of reusing old evidence"
            )
        if run["decision"] or run["status"] in {"ready_for_approval", "needs_attention"}:
            raise HXError("run already reached a handoff; create a new task to continue changes")
        if not resume and run["status"] != "pending":
            raise HXError("use resume for an interrupted, failed or cancelled run")
        if resume:
            if run["resume_count"] >= self.settings.max_resumes:
                raise HXError("resume budget exhausted; create a new run")
            self.store.update(run_id, resume_count=run["resume_count"] + 1)
            self.store.event(
                run_id, "resume.requested", data={"retry_batch": run["resume_count"] + 1}
            )
        started = time.monotonic()
        deadline = started + self.settings.run_timeout_seconds - run["elapsed_seconds"]
        changes = {"status": "running", "error": None}
        if resume:
            changes["cancel_requested"] = False
        self.store.update(run_id, **changes)
        self.store.event(run_id, "run.started")
        task = Task.model_validate(run["task"])
        try:
            candidate = self._implementation(run_id, "implement", task, None, {}, deadline)
            for revision in range(self.settings.max_revisions + 1):
                self.check_control(run_id, deadline)
                validate_candidate(candidate, task)
                verification = self._verify(run_id, revision, candidate, task, deadline)
                single = self.settings.workflow == "single"
                reviews = {} if single else self._reviews(run_id, revision, candidate, task, verification, deadline)
                findings = source_findings(reviews)
                consolidated = Consolidated(candidate_commit=candidate.candidate_commit, groups=[],
                    summary="Single-worker mode: executable verification only.") if single else self._consolidate(
                    run_id, revision, task, candidate, verification, reviews, findings, deadline
                )
                # Model grouping cannot downgrade a source blocker or high/critical severity.
                blockers = [
                    source
                    for source, finding in findings.items()
                    if finding["blocking"] or finding["severity"] in {"high", "critical"}
                ]
                gaps = list(verification.known_gaps)
                if single:
                    gaps.append("No independent model review; passing checks are not proof of task completeness.")
                for role, review in reviews.items():
                    gaps.extend(f"{role}: {gap}" for gap in review.could_not_inspect)
                ready = (
                    verification.passed
                    and not blockers
                    and not any(review.could_not_inspect for review in reviews.values())
                )
                actionable = not verification.passed or bool(blockers)
                if not ready and not actionable:
                    self.store.event(run_id, "revision.skipped", data={
                        "reason": "inspection gaps without a failed check or blocking finding",
                        "known_gaps": gaps,
                    })
                repair_affordable = not single or self.model_headroom(run_id) >= self.settings.repair_token_reserve
                if not ready and not repair_affordable:
                    gaps.append("Further model work stopped: insufficient repair token headroom; candidate and verification preserved.")
                    self.store.event(run_id, "budget.repair_skipped", data={
                        "headroom": self.model_headroom(run_id),
                        "required": self.settings.repair_token_reserve,
                    })
                if ready or revision == self.settings.max_revisions or not actionable or not repair_affordable:
                    handoff = Handoff(
                        run_id=run_id,
                        candidate_commit=candidate.candidate_commit,
                        verified=verification.passed,
                        reviewed=not single,
                        status="ready_for_approval" if ready else "needs_attention",
                        revisions_used=revision,
                        blocking_findings=blockers,
                        known_gaps=gaps,
                        review_steps=[] if single else [f"correctness_{revision}", f"security_{revision}"],
                    )
                    self._handoff(run_id, handoff, candidate, verification, reviews, task, deadline)
                    break
                context = {
                    "verification": verification.model_dump(),
                    "reviews": {role: review.model_dump() for role, review in reviews.items()},
                    "consolidation": consolidated.model_dump(),
                    "repair_plan": {
                        "candidate_commit": candidate.candidate_commit,
                        "failed_checks": [check.model_dump() for check in verification.checks if not check.passed],
                        "blocking_sources": {source: findings[source] for source in blockers},
                        "inspection_gaps": gaps,
                        "instruction": "Repair failed checks and concrete blocking findings; preserve the task's client contract and protected tests. Inspection gaps are unresolved evidence, not permission to invent code requirements. Verify the changed transition and then rerun prescribed checks.",
                    },
                }
                if single:
                    # Keep durable raw evidence in the run; send bounded actionable feedback.
                    context = {"repair_plan": {
                        "candidate_commit": candidate.candidate_commit,
                        "failed_checks": [{"name": c.name, "evidence": focused_output(c.evidence, self.settings.repair_feedback_chars)}
                                          for c in verification.checks if not c.passed][:8],
                        "instruction": "Repair the observed failures. Preserve passing behavior. A test-plan-only correction is allowed; do not invent source changes.",
                    }}
                self.store.event(run_id, "revision.planned", data={
                    "revision": revision + 1,
                    "failed_checks": [check.name for check in verification.checks if not check.passed],
                    "blocking_sources": blockers,
                })
                candidate = self._implementation(
                    run_id, f"revise_{revision + 1}", task, candidate, context, deadline
                )
        except Exception as exc:
            status = "cancelled" if isinstance(exc, Cancelled) else "failed"
            self.store.update(run_id, status=status, error=str(exc))
            self.store.event(run_id, "run." + status, data={"error": str(exc)})
        finally:
            elapsed = run["elapsed_seconds"] + time.monotonic() - started
            self.store.update(run_id, elapsed_seconds=elapsed)
            self.store.export_events(run_id)
        return self.store.get(run_id)

    def _step(
        self,
        run_id: str,
        step_id: str,
        inputs: dict,
        contract: type[BaseModel],
        operation,
        validate,
        deadline: float,
    ):
        key = digest(
            {
                "fingerprint": self.config["fingerprint"],
                "inputs": inputs,
                "step": step_id,
                "contract": contract.model_json_schema(),
            }
        )
        self.check_control(run_id, deadline)
        cached = self.store.cached(run_id, step_id, key)
        if cached is not None:
            try:
                result = contract.model_validate(cached)
                validate(result)
            except (ValueError, ValidationError, HXError) as exc:
                raise GateError(f"replay rejected for {step_id}: {exc}") from exc
            self.store.event(run_id, "step.replayed", step_id, {"cache_key": key})
            return result
        for _ in range(self.settings.max_attempts):
            self.check_control(run_id, deadline)
            attempt = self.store.attempt(run_id, step_id, key)
            directory = self.store.run_dir(run_id) / "steps" / step_id / f"attempt-{attempt}"
            try:
                result = contract.model_validate(operation(directory))
                validate(result)
                self.check_control(run_id, deadline)
                self.store.save(run_id, step_id, key, result.model_dump())
                return result
            except Exception as exc:
                self.store.failed(run_id, step_id, str(exc))
                if isinstance(exc, (StartupError, Cancelled, GateError)):
                    raise
                if _ == self.settings.max_attempts - 1:
                    raise HXError(f"{step_id} exhausted its attempt budget: {exc}") from exc
        raise AssertionError("unreachable")

    def _emit(self, run_id: str, step_id: str):
        def emit(kind: str, data: dict):
            self.store.event(run_id, kind, step_id, data)
            if kind == "worker.usage":
                self.store.add_usage(run_id, int(data["tokens"]))

        return emit

    def _worker(
        self,
        run_id: str,
        step_id: str,
        role: str,
        task: Task,
        workspace: Path,
        context: dict,
        contract: type[BaseModel],
        directory: Path,
        deadline: float,
    ) -> dict:
        if hasattr(self.adapter, "planner"):
            self.adapter.headroom = lambda: self.model_headroom(run_id)
        if self.settings.workflow == "single":
            self.check_control(run_id, deadline)
            if self.model_headroom(run_id) < self.settings.repair_token_reserve:
                raise HXError("insufficient token headroom for another model call")
        if role == "implementer" and self.settings.workflow == "single":
            from hx.environment import snapshot
            from hx.repo_context import inspect

            orientation = inspect(workspace, task.report[:2000], limit=self.settings.repository_matches)
            # Structured bounded context, generated by code on every fresh workspace.
            orientation["test_files"] = orientation["test_files"][:12]
            environment = snapshot()
            context = {**context, "repository_map": orientation, "environment_snapshot": environment}
            self.store.event(run_id, "tool.environment_snapshot", step_id, environment)
            self.store.event(run_id, "tool.repository_map", step_id, {
                "matches": [m["path"] for m in orientation["matches"]],
                "source_scan_truncated": orientation["source_scan_truncated"],
            })
        if task.frontend and role != "consolidator":
            from hx.challenge_eval import prepare_frontend

            prepare_frontend(
                workspace, directory / "dependencies", lambda: self.check_control(run_id, deadline)
            )
            context = {
                **context,
                "frontend_commands": ["npm test -- --maxWorkers=1", "npm run build"],
                "test_environment": "Dependencies are preinstalled. Use writable workspace-local temp/database paths when testing.",
            }
        atomic_write(
            directory / "effective_config.json",
            canonical(
                {
                    "fingerprint": self.config["fingerprint"],
                    "role": role,
                    "settings": self.settings.model_dump(),
                    "cli_version": self.config["cli_version"],
                    "workspace": str(workspace),
                    "adapter": self.adapter.name,
                }
            ),
        )
        return self.adapter.run(
            role,
            task,
            workspace,
            context,
            self.config["prompts"][role],
            contract,
            directory,
            lambda: self.check_control(run_id, deadline),
            self._emit(run_id, step_id),
            min(self.settings.attempt_timeout_seconds, max(0.1, deadline - time.monotonic())),
        )

    def _implementation_contract(self, task):
        return WorkerSummary

    def _candidate_metadata(self, task, summary):
        return {}

    def _implementation(
        self,
        run_id: str,
        step_id: str,
        task: Task,
        previous: Candidate | None,
        feedback: dict,
        deadline: float,
    ) -> Candidate:
        inputs = {
            "task": task.model_dump(),
            "previous": previous.model_dump() if previous else None,
            "feedback": feedback,
        }

        def operation(directory: Path):
            source = Path(previous.workspace) if previous else Path(task.repo)
            commit = previous.candidate_commit if previous else task.base_commit
            repo = self._clone(source, directory / "workspace", commit)
            check_scope(repo, [], task)
            output_contract = self._implementation_contract(task)
            raw = self._worker(
                run_id,
                step_id,
                "implementer",
                task,
                repo,
                {"input_commit": commit, **feedback},
                output_contract,
                directory,
                deadline,
            )
            summary = output_contract.model_validate(raw)
            # WorkerSummary intentionally has no candidate hash or success verdict.
            metadata = self._candidate_metadata(task, summary)
            metadata_changed = previous is not None and any(
                getattr(previous, key) != value for key, value in metadata.items())
            result = derive_with_test_plan(repo, task, commit, previous, summary, metadata_changed)
            result = result.model_copy(update=metadata)
            if previous and result.candidate_commit == previous.candidate_commit:
                self.store.event(run_id, "candidate.test_plan_revised", step_id, {
                    "candidate_commit": result.candidate_commit,
                    "source_changed": False,
                    "previous_commands": previous.verification_commands,
                    "verification_commands": result.verification_commands,
                })
            diff = git(
                repo,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                task.base_commit,
                result.candidate_commit,
            )
            atomic_write(directory / "candidate.patch", diff.encode())
            return result.model_dump()

        return self._step(
            run_id,
            step_id,
            inputs,
            Candidate,
            operation,
            lambda result: validate_candidate(result, task),
            deadline,
        )

    def _verify(
        self, run_id: str, revision: int, candidate: Candidate, task: Task, deadline: float
    ) -> Verification:
        step_id = f"verify_{revision}"

        def operation(directory):
            if self.settings.workflow == "single":
                # Test the actual deliverable against the original source, before tests.
                replay = self._clone(Path(task.repo), directory / "patch-replay", task.base_commit)
                patch = subprocess.check_output([
                    "git", "-C", candidate.workspace, "diff", "--binary", "--no-ext-diff",
                    "--no-textconv", task.base_commit, candidate.candidate_commit,
                ], timeout=30)
                atomic_write(directory / "delivery.patch", patch)
                result = subprocess.run(["git", "-C", str(replay), "apply", "--check", "-"],
                    input=patch, capture_output=True, timeout=30)
                self.store.event(run_id, "tool.patch_replay", step_id, {"passed": result.returncode == 0})
                if result.returncode:
                    from hx.models import Check

                    return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                        checks=[Check(name="patch_apply", passed=False,
                            evidence=result.stderr.decode("utf-8", errors="replace")[-2000:])],
                        changed_line_coverage=None, known_gaps=["Tests not run: patch cannot apply."]).model_dump()
            return self.verifier.run(candidate, task, directory,
                lambda: self.check_control(run_id, deadline), self._emit(run_id, step_id)).model_dump()

        def validate(result: Verification):
            if result.candidate_commit != candidate.candidate_commit:
                raise GateError("verification references a different candidate")
            if result.passed != all(check.passed for check in result.checks) or not result.checks:
                raise GateError("inconsistent verification verdict")
            validate_candidate(candidate, task)

        return self._step(
            run_id,
            step_id,
            {"candidate": candidate.model_dump(), "task": task.model_dump()},
            Verification,
            operation,
            validate,
            deadline,
        )

    def _reviews(
        self,
        run_id: str,
        revision: int,
        candidate: Candidate,
        task: Task,
        verification: Verification,
        deadline: float,
    ) -> dict[str, Review]:
        diff = git(
            Path(candidate.workspace),
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            task.base_commit,
            candidate.candidate_commit,
        )
        if len(diff) > 120000:
            raise GateError("candidate is too large for this small-change workflow")
        context = {
            "candidate_commit": candidate.candidate_commit,
            "diff": diff,
            "verification": verification.model_dump(),
        }

        def review(role: str):
            step_id = f"{role}_{revision}"

            def operation(directory: Path):
                repo = self._clone(
                    Path(candidate.workspace), directory / "workspace", candidate.candidate_commit
                )
                raw = self._worker(
                    run_id, step_id, role, task, repo, context, Review, directory, deadline
                )
                assert_clean(repo, candidate.candidate_commit)
                return raw

            return self._step(
                run_id,
                step_id,
                context,
                Review,
                operation,
                lambda result: validate_review(result, candidate),
                deadline,
            )

        results = {}
        errors = []
        self.store.event(
            run_id,
            "parallel.started",
            data={"steps": [f"{r}_{revision}" for r in ("correctness", "security")]},
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(review, role): role for role in ("correctness", "security")}
            for future in as_completed(futures):
                try:
                    results[futures[future]] = future.result()
                except Exception as exc:
                    errors.append(exc)
                    # Do not discard or cancel the healthy sibling because another branch failed.
        self.store.event(
            run_id,
            "parallel.finished",
            data={"completed": sorted(results), "failures": len(errors)},
        )
        if errors:
            raise errors[0]
        return {role: results[role] for role in ("correctness", "security")}

    def _consolidate(
        self,
        run_id: str,
        revision: int,
        task: Task,
        candidate: Candidate,
        verification: Verification,
        reviews: dict[str, Review],
        findings: dict,
        deadline: float,
    ) -> Consolidated:
        context = {
            "candidate_commit": candidate.candidate_commit,
            "source_findings": findings,
            "reviews": {role: review.model_dump() for role, review in reviews.items()},
            "verification": verification.model_dump(),
        }
        step_id = f"consolidate_{revision}"

        def operation(directory: Path):
            repo = directory / "workspace"
            repo.mkdir(parents=True)
            git(repo, "init")
            return self._worker(
                run_id,
                step_id,
                "consolidator",
                task,
                repo,
                context,
                Consolidated,
                directory,
                deadline,
            )

        return self._step(
            run_id,
            step_id,
            context,
            Consolidated,
            operation,
            lambda result: validate_consolidation(result, findings, candidate.candidate_commit),
            deadline,
        )

    def _handoff(
        self,
        run_id: str,
        handoff: Handoff,
        candidate: Candidate,
        verification: Verification,
        reviews: dict[str, Review],
        task: Task,
        deadline: float,
    ):
        validate_candidate(candidate, task)
        for review in reviews.values():
            validate_review(review, candidate)
        if verification.candidate_commit != candidate.candidate_commit:
            raise GateError("handoff verification is stale")
        self._step(
            run_id,
            "handoff",
            {"candidate": candidate.model_dump(), "handoff": handoff.model_dump()},
            Handoff,
            lambda _: handoff.model_dump(),
            lambda _: validate_candidate(candidate, task),
            deadline,
        )
        summary = (
            f"# {run_id}: {handoff.status}\n\n"
            f"Candidate: `{candidate.candidate_commit}`\n\n"
            f"Verified: {handoff.verified}. Reviewed: {handoff.reviewed}. Approval: pending.\n\n"
            f"Revisions: {handoff.revisions_used}. Blocking findings: {len(handoff.blocking_findings)}.\n\n"
            "Known gaps:\n\n" + "\n".join("- " + gap for gap in handoff.known_gaps) + "\n"
        )
        atomic_write(self.store.run_dir(run_id) / "handoff.md", summary.encode())
        self.store.update(run_id, status=handoff.status, handoff=handoff.model_dump())
        self.store.event(run_id, "handoff.written", data=handoff.model_dump())

    def decision(self, run_id: str, commit: str, approve: bool, reason: str = "") -> dict:
        lock = FileLock(str(self.store.run_dir(run_id) / "execution.lock"))
        try:
            with lock.acquire(timeout=0):
                run = self.store.get(run_id)
                if run["config"]["fingerprint"] != self.config["fingerprint"]:
                    raise GateError("configuration changed since this run")
                if run["decision"]:
                    raise HXError("run already has a human decision")
                if not run["handoff"] or run["status"] not in {
                    "ready_for_approval",
                    "needs_attention",
                }:
                    raise GateError("run has no final handoff")
                handoff = Handoff.model_validate(run["handoff"])
                if commit != handoff.candidate_commit:
                    raise GateError("decision must name the exact handoff commit")
                steps = {row["id"]: row for row in self.store.steps(run_id)}

                def saved(step: str, contract):
                    if step not in steps:
                        raise GateError(f"missing final evidence: {step}")
                    raw = self.store.cached(run_id, step, steps[step]["cache_key"])
                    if raw is None:
                        raise GateError(f"incomplete final evidence: {step}")
                    return contract.model_validate(raw)

                saved_handoff = saved("handoff", Handoff)
                if saved_handoff != handoff:
                    raise GateError("handoff record differs from sealed artifact")
                candidate_step = (
                    "implement"
                    if handoff.revisions_used == 0
                    else f"revise_{handoff.revisions_used}"
                )
                candidate = saved(candidate_step, Candidate)
                validate_candidate(candidate, Task.model_validate(run["task"]))
                if candidate.candidate_commit != commit:
                    raise GateError("final candidate revision mismatch")
                if approve:
                    ver = saved(f"verify_{handoff.revisions_used}", Verification)
                    reviews = {} if self.settings.workflow == "single" else {
                        role: saved(f"{role}_{handoff.revisions_used}", Review)
                        for role in ("correctness", "security")
                    }
                    for review in reviews.values():
                        validate_review(review, candidate)
                    blockers = [
                        finding
                        for review in reviews.values()
                        for finding in review.findings
                        if finding.blocking or finding.severity in {"high", "critical"}
                    ]
                    if (
                        handoff.status != "ready_for_approval"
                        or not ver.passed
                        or not all(check.passed for check in ver.checks)
                        or ver.candidate_commit != commit
                        or blockers
                        or any(review.could_not_inspect for review in reviews.values())
                    ):
                        raise GateError(
                            "candidate has blocking findings, missing review evidence or failed verification"
                        )
                elif not reason.strip():
                    raise HXError("denial requires a reason")
                decision = {
                    "approved": approve,
                    "candidate_commit": commit,
                    "reason": reason,
                    "at": now(),
                }
                self.store.update(
                    run_id, status="approved" if approve else "denied", decision=decision
                )
                self.store.event(run_id, "human.decision", data=decision)
                self.store.export_events(run_id)
                return self.store.get(run_id)
        except Timeout as exc:
            raise HXError("run is currently executing") from exc
