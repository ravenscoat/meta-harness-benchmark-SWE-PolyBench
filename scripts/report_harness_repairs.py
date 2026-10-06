"""Audit closed repaired evaluation from saved scores and public actor traces."""
import json
import re
from pathlib import Path

from benchmarks.polybench.metrics import aggregate
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.runner import lock_sources


def main():
    root = Path(".hx/harness-repair-evaluation-v1").resolve()
    if not (root / "controller.exited.json").exists():
        raise RuntimeError("Evaluation controller has not exited")
    plan = json.loads((root / "batch-plan.json").read_text())
    assert sha(root / "batch-plan.json") == json.loads((root / "batch-plan.lock.json").read_text())["sha256"]
    for name, expected in {**plan["historical_score_sha256"], **plan["scheduler_sha256"]}.items():
        assert sha(Path(name)) == expected, name
    lock_sources(root)
    score_lock = json.loads((root / "score-lock.json").read_text())
    assert all(sha(root / p) == h for p, h in score_lock.items())
    rows = [json.loads((root / p).read_text()) for p in score_lock]
    public = []
    for p in score_lock:
        trial = (root / p).parent
        row = json.loads((trial / "score.json").read_text())
        events = [json.loads(line) for file in (trial / "state/runs").glob("*/events.jsonl")
                  for line in file.read_text().splitlines()]
        actors = [e["data"] for e in events if e["type"] == "worker.instantiated"]
        assert all(a["model"] == "gpt-6-luna" and a["role"] == "implementer" for a in actors)
        navigation = []
        for event in events:
            item = event.get("data", {}).get("item", {})
            command = item.get("command", "")
            if (event["type"] == "worker.event" and item.get("type") == "command_execution"
                    and re.search(r"(?:\S*/)?python(?:\d+(?:\.\d+)?)?\s+/opt/hx-tools/repo_context\.py", command)):
                navigation.append({"command": command, "exit_code": item.get("exit_code")})
        public.append({"case": row["case"], "actors": actors,
            "optional_navigation_invocations": navigation,
            "automatic_tools": sorted({e["type"] for e in events if e["type"].startswith("tool.")}),
            "command_adaptations": [e["data"] for e in events if e["type"] == "tool.public_test_command_adapted"],
            "public_checks": [e["data"] for e in events if e["type"] == "verification.check"],
            "plan_revisions": [e["data"] for e in events if e["type"] == "candidate.test_plan_revised"],
            "delivery": json.loads((trial / "delivery.json").read_text()) if (trial / "delivery.json").exists() else None})
    finish = json.loads((root / "controller.exited.json").read_text())["time"]
    metrics = aggregate(rows, finish - plan["started"])
    write(root / "public-tool-audit.json", public)
    write(root / "audit.json", {"scores_sealed": len(rows),
        "historical_scores_unchanged": len(plan["historical_score_sha256"]),
        "source_and_scheduler_unchanged": True, "all_recorded_actors_luna": True,
        "metrics": metrics, "score_sha256": score_lock,
        "public_audit_sha256": sha(root / "public-tool-audit.json")})
    lines = ["\n## Fresh evaluation outcome\n",
        "| Case | Official resolved | Public verified | Patch rejected | Required tests unobserved | Reported tokens | Workflow seconds |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['case']} | {row['official_resolved']} | {row['visible_verified']} | "
            f"{bool(row.get('candidate_patch_error'))} | {row['unobserved_acceptance_tests']} | "
            f"{row['observed_tokens']:,} | {row['seconds']:.2f} |")
    lines.extend(["", f"Fresh official resolutions: {metrics['official_resolutions']}/{len(rows)}. "
        f"End-to-end successes: {metrics['end_to_end_successes']}/{len(rows)}. "
        f"Reported tokens: {metrics['reported_tokens']:,}; workflow time: {metrics['workflow_seconds']:.2f}s; "
        f"total batch wall time: {metrics['wall_seconds']:.2f}s.",
        "", "Sealed scores, public actor/tool evidence and full efficiency metrics are in the evaluation root's "
        "`audit.json` and `public-tool-audit.json`. Original results remain unchanged. "
        "These fresh tasks are separate from the two recovered development diagnostics. "
        "No baseline arm, causal improvement claim or leaderboard ranking is established."])
    if (root / "stop.json").exists():
        lines.extend(["", "The batch stopped with preserved evidence: " + json.loads((root / "stop.json").read_text())["error"]])
    doc = Path("docs/HARNESS_REPAIR_REPORT.md")
    text = doc.read_text().split("\n## Fresh evaluation outcome\n")[0]
    doc.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(metrics), flush=True)


if __name__ == "__main__":
    main()
