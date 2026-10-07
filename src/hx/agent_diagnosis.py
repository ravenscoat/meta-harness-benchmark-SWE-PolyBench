"""Public development evidence for reusable-program proposals, never grader internals."""
from __future__ import annotations

import json
from pathlib import Path

VERSION = "public-agent-diagnosis@1"


def verification_findings(folder: Path, public: Path) -> list[dict]:
    findings = []
    for path in sorted(folder.glob("public-traces/**/delegate-*/stdout.txt"))[:100]:
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(public)):
            raise ValueError("Symlinked public trace is forbidden")
        if path.stat().st_size > 2_000_000:
            findings.append({"category": "trace_not_inspected", "evidence": path.relative_to(public).as_posix()})
            continue
        for line in path.read_text(errors="replace").splitlines():
            try:
                event = json.loads(line)
                item = event.get("item", {})
                if item.get("type") != "agent_message":
                    continue
                summary = json.loads(item.get("text", ""))
                commands = summary.get("verification_commands", [])
                if not isinstance(commands, list):
                    continue
                for command in commands:
                    if isinstance(command, list) and "--grep" in command and "--invert" in command:
                        findings.append({"category": "filtered_verification", "evidence": path.relative_to(public).as_posix(),
                            "finding": "Submitted verification excludes matching tests; inspect omitted expectations and report unfiltered results. This is a review lead, not proof of a defect."})
            except (ValueError, AttributeError, TypeError):
                continue
    return findings


def diagnose_trial(row: dict, evidence: str) -> dict:
    findings = []
    if not row.get("usage_known"):
        category = "unknown_usage"
    elif row.get("workflow_error") or row.get("infrastructure_error") or row.get("missing_observations"):
        category = "operational_failure"
    elif row.get("patch_error"):
        category = "delivery_rejection"
    elif not row.get("accepted_candidate"):
        category = "no_accepted_candidate"
    elif row.get("official_resolved"):
        category = "official_solve"
    else:
        category = "official_non_solve"
        findings.append("Official aggregate does not reveal the failed assertion; investigate public behavior.")
    if not row.get("public_verified"):
        findings.append("Public verification did not establish readiness; inspect public failure/inconclusive receipts.")
    elif category == "official_non_solve":
        findings.append("Public green and official failure indicate incomplete evidence, not a known hidden cause.")
    # Deliberate whitelist: arbitrary score fields and evaluator payloads never enter proposals.
    return {"category": category, "evidence": evidence, "case": row.get("case"),
            "repeat": row.get("repeat"), "source_sha256": row.get("source_sha256"),
            "official_resolved": row.get("official_resolved"), "public_verified": row.get("public_verified"),
            "reported_tokens": row.get("reported_tokens"), "seconds": row.get("seconds"),
            "findings": findings}


def diagnose_development(public: Path) -> dict:
    """Only controller-created development score paths; no heldout traversal or raw logs."""
    trials = []
    for path in sorted(public.glob("*/case-*-repeat-*/score.json")):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != public.parent):
            raise ValueError("Symlinked development evidence is forbidden")
        trial = diagnose_trial(json.loads(path.read_text()), path.relative_to(public).as_posix())
        trial["trace_findings"] = verification_findings(path.parent, public)
        trials.append(trial)
    counts = {}
    for trial in trials:
        counts[trial["category"]] = counts.get(trial["category"], 0) + 1
    return {"version": VERSION, "scope": "Public development only; no private or heldout assertions",
            "counts": counts, "trials": trials,
            "proposal_rules": [
                "Diagnose public evidence before proposing a reusable program change.",
                "Cite inspected development evidence and explain a general mechanism; never hardcode tasks.",
                "Do not omit failing compatibility checks or invent a private failure cause.",
                "Keep models, budgets, evaluator and task contracts fixed.",
                "Operational failures require stopped-boundary infrastructure repair, not solve-score tuning.",
                "A proposal is a hypothesis; paired development and frozen heldout evaluation decide eligibility."]}
