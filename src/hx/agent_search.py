"""Measured executable-agent search. Trusted backends own models and grading.

The proposer receives only a public development archive, never heldout receipts.
This controller does not execute candidate Python itself or grant credentials.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Protocol

from filelock import FileLock
from pydantic import Field, model_validator

from hx.agent_diagnosis import diagnose_development
from hx.code_search import seal, sha
from hx.config import canonical
from hx.models import Contract, HXError
from hx.store import atomic_write
from hx.worker_scaffold import validate_scaffold


class SearchPlan(Contract):
    development: list[str] = Field(min_length=2)
    heldout: list[str] = Field(min_length=2)
    proposals: int = Field(ge=1, le=10)
    repeats: int = Field(ge=2, le=10)
    max_reported_tokens: int = Field(gt=0)
    deadline: float
    trial_token_headroom: int = Field(gt=0)
    proposal_token_headroom: int = Field(gt=0)
    model: str
    reasoning_effort: str
    # Explicit sealed dataset, settings, scheduler, backend and incumbent files.
    source_locks: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self):
        combined = self.development + self.heldout
        if len(combined) != len(set(combined)):
            raise ValueError("Search and heldout cases must be distinct and disjoint")
        if not math.isfinite(self.deadline):
            raise ValueError("Deadline must be finite")
        return self


class Trial(Contract):
    identity: str = Field(min_length=1)
    case: str
    repeat: int = Field(ge=1)
    source_sha256: str
    model: str
    reasoning_effort: str
    official_resolved: bool
    public_verified: bool
    usage_known: bool
    reported_tokens: int = Field(ge=0)
    seconds: float = Field(ge=0, allow_inf_nan=False)
    infrastructure_error: str | None
    patch_error: str | None
    missing_observations: int = Field(ge=0)
    accepted_candidate: bool
    reference_informed: bool
    workflow_error: str | None = None
    workflow_status: str | None = None


class Proposal(Contract):
    source: str
    hypothesis: str = Field(min_length=20, max_length=3000)
    reported_tokens: int = Field(ge=0)
    usage_known: bool


class Backend(Protocol):
    """Trusted backend: quota/preflights, exact delivery and official scoring.

    evaluate must start a NEW isolated trial, apply the supplied scaffold through
    WorkerScaffoldAdapter and export only explicitly public logs into directory.
    No private tests, reference patches or grader logs may enter that directory.
    propose must isolate public_archive from campaign root and filesystem parents.
    Its output may change ONLY the scaffold; model/settings/evaluator stay fixed.
    Both operations must invoke control at model-call and usage boundaries. Guards
    are turn-boundary limits and cannot prevent an in-flight overshoot.
    """

    def admit(self, plan: SearchPlan) -> None: ...

    def evaluate(self, source: Path, case: str, repeat: int, directory: Path,
                 plan: SearchPlan, control) -> Trial: ...

    def propose(self, public_archive: Path, directory: Path,
                plan: SearchPlan, control) -> Proposal: ...


def metrics(rows: list[Trial]) -> dict:
    return {"official_resolutions": sum(r.official_resolved for r in rows),
            "trials": len(rows), "reported_tokens": sum(r.reported_tokens for r in rows),
            "seconds": sum(r.seconds for r in rows)}


def dominates(a: dict, b: dict) -> bool:
    fields = ("reported_tokens", "seconds")
    return (a["official_resolutions"] >= b["official_resolutions"]
            and all(a[k] <= b[k] for k in fields)
            and (a["official_resolutions"] > b["official_resolutions"]
                 or any(a[k] < b[k] for k in fields)))


def promotable(candidate: list[Trial], baseline: list[Trial]) -> bool:
    # Conservative paired guard: aggregate gains cannot conceal lost cases.
    pairs = {(r.case, r.repeat): r for r in baseline}
    return (len(candidate) == len(baseline) and bool(candidate)
            and {(r.case, r.repeat) for r in candidate} == set(pairs)
            and all(not pairs[r.case, r.repeat].official_resolved or r.official_resolved
                    for r in candidate)
            and dominates(metrics(candidate), metrics(baseline)))


def run_search(root: Path, plan: SearchPlan, incumbent: Path, backend: Backend) -> dict:
    """New identities only. No resume, hidden retries, automatic source install.

    A failed proposal is retained and consumes an iteration. Operational/unknown
    usage failures stop the campaign, preserving partial receipts. Heldout runs
    are never exported to subsequent proposers in this campaign.
    """
    root = root.resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root.parent / "single-evaluation-controller.lock"), timeout=0):
        if root.exists():
            raise HXError("New agent-search root required; consumed roots cannot restart")
        root.mkdir()
        atomic_write(root / "plan.json", canonical(plan.model_dump()))
        atomic_write(root / "plan.lock.json", canonical({"sha256": sha((root / "plan.json").read_bytes())}))
        public = root / "development"
        public.mkdir()
        used, identities, all_rows, archive = 0, set(), {}, {}
        phase = "preparation"
        result = None

        def save(path, value):
            atomic_write(path, canonical(value))

        def control(headroom=0):
            if time.time() >= plan.deadline or used + headroom > plan.max_reported_tokens:
                raise HXError("Agent search budget/deadline exhausted; no extension")
            for name, expected in plan.source_locks.items():
                if sha(Path(name).read_bytes()) != expected:
                    raise HXError("Locked source changed: " + name)
            if sha((root / "plan.json").read_bytes()) != sha(canonical(plan.model_dump())):
                raise HXError("Search plan changed")
            current = seal(public)
            if any(current.get(k) != v for k, v in archive.items()):
                raise HXError("Public search experience changed")

        def evaluate(name, source, cases, destination):
            nonlocal used, archive
            rows = []
            expected_hash = sha(source.read_bytes())
            for case_index, case in enumerate(cases):
                for repeat in range(1, plan.repeats + 1):
                    control(plan.trial_token_headroom)
                    backend.admit(plan)
                    folder = destination / name / f"case-{case_index}-repeat-{repeat}"
                    folder.mkdir(parents=True, exist_ok=False)
                    # Mark consumed BEFORE a backend can start a model.
                    save(folder / "started.json", {"case": case, "repeat": repeat,
                                                   "source_sha256": expected_hash})
                    row = Trial.model_validate(backend.evaluate(source, case, repeat, folder, plan, control))
                    save(folder / "score.json", row.model_dump())
                    used += row.reported_tokens
                    all_rows.setdefault(name + "/" + phase, []).append(row.model_dump())
                    save(root / "usage.json", {"reported_tokens": used, "usage_known": row.usage_known})
                    if (row.identity in identities or row.case != case or row.repeat != repeat
                            or row.source_sha256 != expected_hash or sha(source.read_bytes()) != expected_hash
                            or row.model != plan.model or row.reasoning_effort != plan.reasoning_effort):
                        raise HXError("Trial identity/source/model mismatch")
                    identities.add(row.identity)
                    if (not row.usage_known or row.infrastructure_error or row.workflow_error or row.missing_observations
                            or row.reference_informed):
                        raise HXError("Operational, unknown-usage or contaminated trial; stopping")
                    if row.official_resolved and (not row.accepted_candidate or row.patch_error):
                        raise HXError("Official success contradicts delivery receipt")
                    rows.append(row)
                    # New logs are allowed, modification of prior public logs is not.
                    if destination == public:
                        current = seal(public)
                        if any(current.get(k) != v for k, v in archive.items()):
                            raise HXError("Prior public experience overwritten")
                        archive = current
                    control()
            return rows

        try:
            control()
            data = incumbent.read_bytes()
            if plan.source_locks.get(str(incumbent.resolve())) != sha(data):
                raise HXError("Incumbent must be explicitly source-locked")
            validate_scaffold(data)
            baseline_source = root / "baseline.py"
            atomic_write(baseline_source, data)
            atomic_write(public / "baseline.py", data)
            archive = seal(public)
            phase = "development"
            baseline = evaluate("baseline", baseline_source, plan.development, public)
            scores = {"baseline": metrics(baseline)}
            candidates = {"baseline": (baseline_source, baseline)}
            seen_sources = {sha(data)}
            for iteration in range(1, plan.proposals + 1):
                control(plan.proposal_token_headroom)
                backend.admit(plan)
                # Append an immutable evidence snapshot before each proposal. Heldout is
                # never traversed or exported; infrastructure defects have already stopped.
                diagnosis = diagnose_development(public)
                save(public / f"diagnosis-{iteration}.json", diagnosis)
                archive = seal(public)
                proposal_dir = root / "proposals" / str(iteration)
                proposal_dir.mkdir(parents=True)
                save(proposal_dir / "started.json", {"iteration": iteration})
                proposal = Proposal.model_validate(backend.propose(public, proposal_dir, plan, control))
                used += proposal.reported_tokens
                save(proposal_dir / "proposal.json", proposal.model_dump())
                save(root / "usage.json", {"reported_tokens": used, "usage_known": proposal.usage_known})
                if not proposal.usage_known:
                    raise HXError("Unknown proposer usage; stopping")
                control()
                if seal(public) != archive:
                    raise HXError("Proposer changed public experience")
                save(public / f"proposal-{iteration}.json", proposal.model_dump())
                # Proposal logs contain only isolated public search inputs.
                for filename in ("prompt.txt", "stdout.txt", "stderr.txt"):
                    log = proposal_dir / "model" / filename
                    if log.is_file() and not log.is_symlink():
                        atomic_write(public / f"proposal-{iteration}-{filename}", log.read_bytes())
                archive = seal(public)
                source = proposal_dir / "candidate.py"
                candidate_data = proposal.source.encode("utf-8")
                atomic_write(source, candidate_data)
                try:
                    validate_scaffold(candidate_data)
                    if sha(candidate_data) in seen_sources:
                        raise HXError("Duplicate source; no identical candidate evaluation")
                except (HXError, SyntaxError) as error:
                    save(proposal_dir / "rejection.json", {"error": str(error)})
                    save(public / f"proposal-{iteration}-rejection.json", {"error": str(error)})
                    archive = seal(public)
                    continue
                seen_sources.add(sha(candidate_data))
                name = f"candidate-{iteration}"
                # Proposer history includes executable source and hypothesis.
                atomic_write(public / f"{name}.py", candidate_data)
                save(public / f"{name}.json", {"hypothesis": proposal.hypothesis})
                archive = seal(public)
                rows = evaluate(name, source, plan.development, public)
                scores[name] = metrics(rows)
                candidates[name] = (source, rows)
                save(root / "development-scores.json", scores)
            eligible = [name for name in candidates if name != "baseline"
                        and promotable(candidates[name][1], baseline)]
            frontier = sorted(name for name in scores if not any(
                dominates(other, scores[name]) for key, other in scores.items() if key != name))
            winner = min(eligible, key=lambda n: (-scores[n]["official_resolutions"],
                         scores[n]["reported_tokens"], scores[n]["seconds"], n)) if eligible else "baseline"
            winner_source = candidates[winner][0]
            selection = {"winner": winner, "source_sha256": sha(winner_source.read_bytes()),
                         "frontier": frontier, "development_scores": scores}
            save(root / "selection.json", selection)
            selection_hash = sha((root / "selection.json").read_bytes())
            # Freeze BEFORE heldout; no more proposals, even if heldout rejects.
            phase = "heldout"
            promoted = False
            if winner != "baseline":
                heldout_baseline = evaluate("baseline", baseline_source, plan.heldout, root / "heldout")
                heldout_candidate = evaluate(winner, winner_source, plan.heldout, root / "heldout")
                promoted = promotable(heldout_candidate, heldout_baseline)
            control()
            if sha((root / "selection.json").read_bytes()) != selection_hash:
                raise HXError("Frozen selection changed")
            result = {"complete": True, "eligible_for_promotion": promoted,
                      "winner": winner, "reported_tokens": used, "rows": all_rows,
                      "limitation": "Small paired sample; no causal or leaderboard claim. No automatic install."}
            save(root / "report.json", result)
            if promoted:
                atomic_write(root / "promoted-scaffold.py", winner_source.read_bytes())
        except BaseException as error:
            save(root / "failure.json", {"phase": phase, "error": str(error),
                                        "reported_tokens": used, "rows": all_rows,
                                        "eligible_for_promotion": False,
                                        "usage_known": False,
                                        "limitation": "Unreturned calls may have unknown usage; never resume."})
            raise
        finally:
            save(root / "archive-lock.json", {"files": seal(root)})
        return result
