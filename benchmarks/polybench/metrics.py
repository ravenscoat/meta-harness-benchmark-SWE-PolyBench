"""Outcome and efficiency measures that never confuse absent tests with a pass."""
from collections import Counter


def classification(row):
    if row.get("grader_error"):
        return "grading_infrastructure_error"
    if row.get("candidate_patch_error"):
        return "patch_rejected"
    if not (row.get("acceptance") or {}).get("candidate_commit"):
        return "no_accepted_candidate"
    if row.get("official_resolved"):
        return "official_resolution"
    if row.get("unobserved_acceptance_tests"):
        return "required_tests_unobserved"
    return "observed_official_failure"


def aggregate(rows, wall_seconds=None):
    successes = sum(bool(r.get("official_resolved")) for r in rows)
    ready = [r for r in rows if r.get("status") == "ready_for_approval"]
    tokens = sum(r.get("observed_tokens", 0) for r in rows)
    workflow = sum(r.get("seconds", 0) for r in rows)
    return {"attempts": len(rows), "official_resolutions": successes,
        "end_to_end_successes": sum(bool(r.get("task_success")) for r in rows),
        "outcomes": dict(Counter(classification(r) for r in rows)),
        "ready_claims": len(ready),
        "ready_claims_officially_resolved": sum(bool(r.get("official_resolved")) for r in ready),
        "readiness_precision": sum(bool(r.get("official_resolved")) for r in ready) / len(ready) if ready else None,
        "reported_tokens": tokens, "workflow_seconds": workflow, "wall_seconds": wall_seconds,
        "reported_tokens_per_official_resolution": tokens / successes if successes else None,
        "workflow_seconds_per_official_resolution": workflow / successes if successes else None,
        "wall_seconds_per_official_resolution": wall_seconds / successes if successes and wall_seconds is not None else None,
        "notes": ["Undefined efficiency/precision is null, never zero.",
            "Reported tokens are usage, not dollars; workflow time excludes downloads/grading.",
            "Public readiness is not official correctness; rejected patches lack behavioral observations."]}
