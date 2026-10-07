from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from benchmarks.polybench.containers import ContainerAdapter, command, create, populate
from benchmarks.polybench.contract_coverage import (
    LIMITATION as COVERAGE_LIMITATION,
)
from benchmarks.polybench.contract_coverage import (
    CoverageSummary,
    coverage_check,
    evidence_plan,
)
from benchmarks.polybench.contract_coverage import (
    inventory as contract_inventory,
)
from benchmarks.polybench.dependencies import prepare_dependencies, share_public_fixture
from benchmarks.polybench.public_checks import public_test_contract, public_test_execution
from benchmarks.polybench.regression import LIMITATION, regression_check
from benchmarks.polybench.report_capture import capture_argv
from benchmarks.polybench.test_environment import docker_environment
from benchmarks.polybench.worker_environment import build_check
from hx.check_execution import command_check
from hx.config import digest
from hx.engine import Engine
from hx.git import assert_clean, clone, git
from hx.models import Check, Consolidated, Contract, Task, Verification
from hx.process import clean_env


class Policy(Contract):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,48}$")
    hypothesis: str = Field(min_length=10, max_length=2000)
    guidance: str = Field(max_length=5000)
    inventory: bool
    context_files: list[Literal["README.md", "CONTRIBUTING.md", "package.json", "pyproject.toml",
                                "setup.cfg", "setup.py", "pytest.ini", "tsconfig.json"]] = Field(max_length=6)


BASE_POLICY = Policy(name="current", hypothesis="Current HX with common repository adapter",
                     guidance="", inventory=False, context_files=[])


class VisibleVerifier:
    version = "polybench-public-tests@13"

    def __init__(self, settings, client, case):
        self.settings, self.client, self.case = settings, client, case

    def run(self, candidate, task, directory, check_control, emit):
        bootstrap = self.case.get("repo") in {"huggingface/transformers", "microsoft/vscode"}
        container, workdir = create(self.client, self.case, offline=not bootstrap)
        removed = False
        try:
            if bootstrap:
                # Public dependency preparation precedes candidate source and offline tests.
                check_control()
                prepare_dependencies(container, self.case["repo"], directory / "dependencies",
                    self.case["upstream_base"])
                share_public_fixture(container, self.case["repo"])
                container.reload()
                for network in list(container.attrs["NetworkSettings"]["Networks"]):
                    self.client.networks.get(network).disconnect(container)
                container.reload()
                if container.attrs["NetworkSettings"]["Networks"]:
                    raise RuntimeError("public verification container did not become offline")
            populate(container, workdir, Path(candidate.workspace), self.case)
            checks = []
            public_checks = []
            gaps = ["Public tests are selected by the worker and replayed by HX. Passing them does not establish task completeness; independent benchmark tests run separately after the workflow."]
            build = build_check(container, workdir, Path(candidate.workspace), self.case,
                directory / "public-build", self.settings, check_control, emit)
            if build:
                checks.append(build)
                if not build.passed:
                    return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                        checks=checks, changed_line_coverage=None,
                        known_gaps=gaps + ["Functional tests deferred: candidate public build prerequisite failed."])
            for name, argv in [("patch_whitespace", ["git", "diff", "--check", task.base_commit, "HEAD"])]:
                checks.append(command_check(name,
                    ["docker", "exec", "-w", workdir, container.id, *argv], directory,
                    clean_env(), directory / name, self.settings, check_control, emit))
            python_files = [f for f in candidate.changed_files if f.endswith(".py")
                            and (Path(candidate.workspace) / f).is_file()]
            if python_files:
                python = command(container, ["sh", "-c", "command -v python || command -v python3"]).decode().strip()
                checks.append(command_check("changed_python_syntax",
                    ["docker", "exec", "-u", "1000:1000", "-e", "HOME=/tmp/hx-home",
                     "-w", workdir, container.id, python, "-m", "py_compile", *python_files],
                    directory, clean_env(), directory / "syntax", self.settings, check_control, emit))
            commands = candidate.verification_commands
            if not commands:
                checks.append(Check(name="public_test_plan", passed=False,
                    evidence="No public test command supplied. Select an installed repository test runner and return verification_commands as argv lists; syntax and whitespace do not validate behavior."))
            for index, argv in enumerate(commands):
                name = f"public_test_{index + 1}"
                try:
                    actual, environment, changes = public_test_execution(argv, Path(candidate.workspace))
                except ValueError:
                    failed = Check(name=name, passed=False,
                        evidence=f"Unsupported public test runner: {argv!r}. Use pytest, python -m pytest, npm/yarn/pnpm test or run test:<script>/test-<script>, installed mocha/jest/vitest, yarn/pnpm mocha/jest/vitest, or node --test.")
                    checks.append(failed)
                    public_checks.append(failed)
                    continue
                if changes:
                    emit("tool.public_test_command_adapted", {"name": name,
                        "original_argv": argv, "executed_argv": actual,
                        "environment": environment, "reasons": changes})
                    gaps.extend(c for c in changes if "cleanup remains unverified" in c)
                checks.append(command_check(name,
                    ["docker", "exec", "-u", "1000:1000", *docker_environment(),
                     *[v for k, value in environment.items() for v in ("-e", k + "=" + value)],
                     "-w", workdir, container.id, *capture_argv(actual, self.settings.max_log_bytes)],
                    directory, clean_env(), directory / name, self.settings, check_control, emit))
                public_checks.append(checks[-1])
            if all(c.passed for c in checks):
                # A second disposable container restores original production source
                # and overlays only public test changes. No additional model call.
                container.remove(force=True)
                removed = True
                checks.append(regression_check(candidate, task, directory / "base_replay",
                    self.settings, self.client, self.case, check_control, emit))
                gaps.append(LIMITATION)
            else:
                gaps.append("Base reproduction replay deferred until candidate public checks pass.")
            checks.append(coverage_check(candidate, task, directory, public_checks, emit))
            gaps.append(COVERAGE_LIMITATION)
            assert_clean(Path(candidate.workspace), candidate.candidate_commit)
            return Verification(candidate_commit=candidate.candidate_commit,
                passed=all(c.passed for c in checks), checks=checks,
                changed_line_coverage=None, known_gaps=gaps)
        finally:
            if not removed:
                container.remove(force=True)


class PolyEngine(Engine):
    def _implementation_contract(self, task):
        return CoverageSummary

    def _candidate_metadata(self, task, summary):
        return {"public_contract": evidence_plan(task.report, summary.contract_cases)}

    def __init__(self, store, settings, client, case, binary, auth, policy=BASE_POLICY, worker_scaffold=None):
        super().__init__(store, settings, ContainerAdapter(settings, client, case, binary, auth))
        if worker_scaffold is not None:
            from hx.worker_scaffold import VERSION, WorkerScaffoldAdapter
            self.adapter = WorkerScaffoldAdapter(self.adapter, worker_scaffold, settings)
            self.config['worker_scaffold'] = {'version': VERSION,
                'sha256': self.adapter.planner.sha256, 'max_worker_calls': 2, 'max_inspections': 2}
        self.policy, self.case = policy, case
        self.verifier = VisibleVerifier(settings, client, case)
        self.config.update({"policy": policy.model_dump(), "blueprint": "polybench-container@1",
            "image": case["image_id"], "original_base": case["upstream_base"],
            "codex_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "cli_companions": {str(p.relative_to(binary.parent.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(binary.parent.parent.rglob("*")) if p.is_file() and p != binary},
            "protocol": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(Path(__file__).parent.glob("*.py"))}})
        self.config["fingerprint"] = digest({k: v for k, v in self.config.items() if k != "fingerprint"})

    def _clone(self, source, destination, commit):
        root = self.case.get("execution_root")
        if root:
            address = hashlib.sha256(str(destination.resolve()).encode()).hexdigest()
            destination = Path(root) / "workspaces" / address
        return clone(source, destination, commit)

    def _worker(self, run_id, step_id, role, task, workspace, context, contract, directory, deadline):
        self.adapter.workflow_deadline = deadline
        context = {**context, "repository": self.case["repo"], "language": self.case["language"],
            "test_environment": "This is the upstream benchmark dependency image. Use existing public tests and tooling; do not assume a FastAPI/frontend layout. Private acceptance is not available inside this container."}
        if role == "implementer":
            context["public_test_runner_contract"] = public_test_contract()
            if task.kind in {"bug", "feature"}:
                context["public_contract_inventory"] = contract_inventory(task.report)
                context["public_contract_evidence_rules"] = (
                    "Return contract_cases covering every requirement/scenario in the supplied inventory. "
                    "The inventory is derived by HX from the original public issue before your edits. "
                    "For boundary requirements, test below, at and above the relevant boundary with distinct "
                    "named tests (parameterized case IDs count separately). Each case states the actual assertion. "
                    "Each obligation needs a distinct passing test identity observed by HX, not a summary count "
                    "or a repeat of the same test in another command. Use pytest -vv (test_id pytest:path::Class::test), "
                    "Mocha --reporter json (test_id mocha:fullTitle), or Jest --json / Vitest --reporter=json "
                    "(test_id js:fullName). Keep the existing three-command limit. Skipped/xfail tests do not qualify. "
                    "Missing, stale, duplicate or unobserved coverage blocks readiness and enters bounded repair. "
                    "Do not invent passing evidence. Coverage mapping is not permission to alter requested behavior.")
            context["verification_contract"] = (
                "Return up to three focused public test commands in verification_commands, each an argv list. "
                "Each list starts with the executable, never environment assignments or shell syntax. "
                "HX sets BABEL_DISABLE_CACHE=1 and public offline cache paths in both worker and verifier. "
                "Your regression-test edits are retained for public verification; benchmark delivery excludes conventional "
                "test paths so the independent evaluator can install its own tests. Production code must not depend on your tests. "
                "HX will independently replay these in a fresh offline candidate container and feed failures into revision. "
                "For bug AND feature tasks, HX also replays your public test changes against original production code in a second "
                "offline container. At least one command must show a recognized behavioral test failure there, while "
                "your candidate passes every command. Import/collection errors, hangs and empty runs are not reproduction. "
                "Use existing test runners and public test paths; only conventional test-path edits enter the base replay. "
                "Red/green alone does not establish issue coverage: test the actual reported target and state transitions. "
                "Use installed pytest, npm/yarn/pnpm test or run test:<script>/test-<script>, installed mocha/jest/vitest (including ./node_modules/.bin/), yarn/pnpm mocha/jest/vitest, or node --test. "
                "This list is for functional tests ONLY: do not include git diff --check, compile, lint or build commands; "
                "HX already runs its smoke checks and declared public build prerequisites separately. "
                "If worker_environment contains public_build_recipe, rebuild using its argv after production-source edits "
                "before testing; the initial preflight build predates your edits. HX independently rebuilds again in replay. "
                "An empty plan fails verification. Choose a focused regression for the requested behavior and relevant existing "
                "compatibility tests when feasible within three commands and existing deadlines; report gaps honestly. "
                "Trace supported input forms, defaults and lifecycle transitions in the affected public code before choosing tests. "
                "A single happy-path assertion is insufficient when the issue describes boundary cases or multiple components. "
                "During revision, if the only failure is an invalid test command, correct the command list without fabricating a source edit. "
                "If a behavioral test fails, diagnose the behavior and repair the actual implementation. "
                "Do not reference private grader tests or install dependencies.")
            context["harness_guidance"] = self.policy.guidance
            if self.policy.inventory:
                context["tracked_files_prefix"] = git(workspace, "ls-files")[:12000]
            context["selected_source"] = {
                p: (workspace / p).read_text("utf-8", errors="replace")[:12000]
                for p in self.policy.context_files if (workspace / p).is_file()
            }
        return super()._worker(run_id, step_id, role, task, workspace, context, contract, directory, deadline)

    def _consolidate(self, run_id, revision, task, candidate, verification, reviews, findings, deadline):
        if not findings:
            self.check_control(run_id, deadline)
            self.store.event(run_id, "consolidation.skipped", data={
                "reason": "No source findings to group; verification failures and inspection gaps remain unchanged.",
            })
            return Consolidated(candidate_commit=candidate.candidate_commit, groups=[],
                                summary="No source findings to consolidate.")
        return super()._consolidate(run_id, revision, task, candidate, verification, reviews, findings, deadline)

    def one_shot(self, run_id):
        run = self.store.get(run_id)
        task = Task.model_validate(run["task"])
        start = time.monotonic()
        deadline = start + self.settings.run_timeout_seconds
        self.store.update(run_id, status="running")
        try:
            candidate = self._implementation(run_id, "implement", task, None, {}, deadline)
            verification = self._verify(run_id, 0, candidate, task, deadline)
            self.store.update(run_id, status="baseline_complete", baseline_candidate=candidate.model_dump(),
                              baseline_verified=verification.passed)
        except Exception as exc:
            self.store.update(run_id, status="failed", error=str(exc))
        finally:
            self.store.update(run_id, elapsed_seconds=time.monotonic() - start)
            self.store.export_events(run_id)
        return self.store.get(run_id)


def task_for(root: Path, case):
    public = json.loads((root / "public" / (case["id"] + ".json")).read_text())
    return Task(id=case["id"].replace(".", "-"), repo=case["repo_path"], report=public["problem_statement"],
        base_commit=case["sanitized_base"], kind="feature" if case["category"] == "Feature" else "bug",
        allowed_paths=["**"], protected_paths=["__hx_private/**"])
