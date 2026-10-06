"""A bounded Sol outer loop. Only public evidence and constrained runtime knobs."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from hx.adapters import CodexAdapter
from hx.config import canonical, digest
from hx.git import git
from hx.models import Contract, HXError, Settings, Task, Verification
from hx.store import atomic_write


def export_public_runs(store, limit=20) -> list[dict]:
    """Build outer-loop input from runtime evidence, without raw model/grader logs."""
    rows = []
    for run in store.list()[:limit]:
        if run["status"] in {"pending", "running"}:
            continue
        verification = []
        for step in store.steps(run["id"]):
            if not step["id"].startswith("verify_") or step["status"] != "completed":
                continue
            raw = store.cached(run["id"], step["id"], step["cache_key"])
            checked = Verification.model_validate(raw)
            verification.append({"checks": [{"name": c.name, "passed": c.passed,
                "tail": c.evidence[-1500:]} for c in checked.checks
                if "acceptance" not in c.name.lower() and "private" not in c.name.lower()]})
        rows.append({"case": run["id"], "public_verification": verification,
            "navigation_references": ["automatic"] if any(e["type"] == "tool.repository_map"
                for e in store.events(run["id"])) else [],
            "plan_revisions": [e["data"] for e in store.events(run["id"])
                if e["type"] == "candidate.test_plan_revised"], "reviews": []})
    if not rows:
        raise HXError("No completed public run evidence; no Sol call needed")
    return rows


class Proposal(Contract):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,48}$")
    rationale: str = Field(min_length=20, max_length=3000)
    priorities: list[Literal["budget", "test_runner", "fixtures", "patch_delivery",
        "regression_breadth", "context"]] = Field(min_length=1, max_length=6)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    repository_matches: int = Field(ge=3, le=8)
    repair_feedback_chars: int = Field(ge=800, le=2500)
    repair_token_reserve: int = Field(ge=5000, le=80000)
    limitations: list[str] = Field(min_length=1, max_length=8)


def public_evidence(path: Path) -> dict:
    """Strict public-audit projection: never traverse raw experiment directories."""
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise HXError("public evidence exceeds size limit")
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows or len(rows) > 30:
        raise HXError("expected a bounded public-evidence audit list")
    cases = []
    for row in rows:
        checks = [{"name": c["name"], "passed": c["passed"], "tail": c["tail"][-1500:]}
            for v in row.get("public_verification", [])[:3] for c in v.get("checks", [])[:5]]
        cases.append({"id": row["case"], "public_checks": checks,
            "navigation_used": bool(row.get("navigation_references")),
            "plan_revision_count": len(row.get("plan_revisions", [])),
            "review_inspection_gaps": [g[:800] for review in row.get("reviews", [])[:3]
                for g in review.get("gaps", [])[:3]]})
    return {"source_sha256": digest(json.loads(raw)), "cases": cases,
        "limits": "Public workflow observations only. Reviewer claims are unconfirmed unless tested. No private grader content or test solutions."}


def propose(evidence: dict, root: Path, settings: Settings, adapter=None,
            max_tokens: int = 25000, timeout: int = 180) -> Proposal:
    if root.exists():
        raise HXError("meta attempt already exists; never overwrite a proposal")
    root.mkdir(parents=True)
    workspace = root / "workspace"
    workspace.mkdir()
    git(workspace, "init")
    atomic_write(root / "evidence.json", canonical(evidence))
    tokens = 0
    deadline = time.monotonic() + timeout
    def control():
        if time.monotonic() >= deadline:
            raise HXError("Sol proposal deadline exhausted")
        # Usage is final-turn reported. Persist it even if an overshoot rejects adoption.
        if tokens > max_tokens:
            raise HXError("Sol proposal exceeded reported-token allowance")
    def emit(kind, data):
        nonlocal tokens
        if kind == "worker.usage":
            tokens += int(data["tokens"])
        with (root / "events.jsonl").open("ab") as stream:
            stream.write(canonical({"kind": kind, "data": data}) + b"\n")
        atomic_write(root / "usage.json", canonical({"tokens": tokens, "max_tokens": max_tokens}))
    meta_settings = settings.model_copy(update={"judgment_model": "gpt-6.1-sol"})
    adapter = adapter or CodexAdapter(meta_settings)
    instructions = (
        "You are the outer meta harness. Analyze the supplied historical public failure evidence. "
        "Return one bounded runtime configuration proposal matching the schema. Workers remain one gpt-6-luna. "
        "Choose repository context size, failed-check feedback size, and token headroom required for a repair. "
        "These knobs are enforced by Python, not prose. Do not change models, scoring, verification, scope, "
        "repository_matches MUST be 3..8; repair_feedback_chars MUST be 800..2500, NEVER 4000 or 8000. "
        "repair_token_reserve MUST be 5000..80000. Rationale must describe the SAME numeric values you return. "
        "repair_token_reserve is minimum available tokens BEFORE starting another model call; it does NOT "
        "guarantee tokens are reserved during the initial call, because usage is only final-turn reported. "
        "task answers, or budgets. Prioritize concrete mechanisms and costs. Public tests passing does not "
        "prove task success. Reviewer speculation is not observed behavior. No file edits or network. "
        "Reference only supplied case IDs. Configuration acceptance is a regression gate, not proof of improved solves."
    )
    task = Task(id="sol-meta-review", repo=str(workspace), report="Improve runtime efficiency and failure recovery from public historical evidence.")
    try:
        raw = adapter.run("consolidator", task, workspace, {"evidence": evidence,
            "current_runtime": {key: getattr(settings, key) for key in (
                "repository_matches", "repair_feedback_chars", "repair_token_reserve")},
            "allowed_ranges": {"repository_matches": [3, 8], "repair_feedback_chars": [800, 2500],
                "repair_token_reserve": [5000, 80000]}},
            instructions, Proposal, root / "sol", control, emit, timeout)
        proposal = Proposal.model_validate(raw)
        control()
        ids = {c["id"] for c in evidence["cases"]}
        if not set(proposal.evidence_ids) <= ids:
            raise HXError("Sol referenced evidence not supplied")
        if git(workspace, "status", "--porcelain") or git(workspace, "remote"):
            raise HXError("Sol modified its read-only proposal workspace")
        atomic_write(root / "proposal.json", canonical(proposal.model_dump()))
        atomic_write(root / "proposal-lock.json", canonical({"sha256": digest(proposal.model_dump()),
            "evidence_sha256": digest(evidence), "model": "gpt-6.1-sol"}))
        return proposal
    except Exception as exc:
        atomic_write(root / "failure.json", canonical({"error": str(exc), "tokens": tokens}))
        raise


def candidate_settings(settings: Settings, proposal: Proposal) -> Settings:
    # A numeric assertion about a knob must agree with the executable value.
    for match in re.finditer(r"feedback from (\d+) to (\d+)", proposal.rationale, re.I):
        if int(match[2]) != proposal.repair_feedback_chars:
            raise HXError("proposal rationale contradicts executable feedback setting")
    value = settings.model_dump()
    value.update({key: getattr(proposal, key) for key in (
        "repository_matches", "repair_feedback_chars", "repair_token_reserve")})
    value["workflow"] = "single"
    if value["repair_token_reserve"] >= value["max_observed_tokens"]:
        raise HXError("proposal leaves no model-call headroom")
    return Settings.model_validate(value)


def settings_toml(settings: Settings) -> bytes:
    return ("\n".join(f"{key} = {json.dumps(value)}" for key, value in settings.model_dump().items()) + "\n").encode()
