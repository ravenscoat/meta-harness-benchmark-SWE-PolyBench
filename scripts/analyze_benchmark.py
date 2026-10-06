"""Derive paired comparisons from sealed campaign scores without changing trials."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from hx.config import canonical
from hx.store import atomic_write


def provider_interrupted(row):
    message = str(row.get("error") or "").lower()
    return "usage limit" in message or "rate limit" in message


def analyze(directory: Path):
    report = json.loads((directory / "report.json").read_text("utf-8"))
    rows = report["rows"]
    paired = {}
    for split in ("search", "heldout"):
        by_arm = defaultdict(dict)
        for row in rows:
            if row["split"] == split:
                by_arm[row["arm"]][(row["case"], row["repeat"])] = row
        comparisons = [("single", "full")]
        if "improved" in by_arm:
            comparisons.append(("full", "improved"))
        comparisons += [("full", arm) for arm in by_arm if arm.startswith("tuned-")]
        for baseline, treatment in comparisons:
            common = sorted(by_arm[baseline].keys() & by_arm[treatment].keys())
            if not common:
                continue
            wins = losses = both_pass = both_fail = 0
            outcomes = []
            for key in common:
                a, b = by_arm[baseline][key], by_arm[treatment][key]
                before, after = a["task_success"], b["task_success"]
                wins += not before and after
                losses += before and not after
                both_pass += before and after
                both_fail += not before and not after
                outcomes.append(
                    {"task": key[0], "repeat": key[1], "before": before, "after": after}
                )
            paired[f"{split}/{baseline}->{treatment}"] = {
                "paired_trials": len(common),
                "improved": wins,
                "regressed": losses,
                "both_pass": both_pass,
                "both_fail": both_fail,
                "difference_percentage_points": 100 * (wins - losses) / len(common),
                "outcomes": outcomes,
            }
    failures = [
        {
            "arm": r["arm"],
            "split": r["split"],
            "task": r["case"],
            "repeat": r["repeat"],
            "failed_groups": [g for g, passed in r["acceptance"]["groups"].items() if not passed],
            "runtime_error": r["error"],
            "provider_interrupted": provider_interrupted(r),
            "status": r["status"],
            "run_id": r["run_id"],
        }
        for r in rows
        if not r["task_success"]
    ]
    workflow = {}
    for row in rows:
        key = f"{row['split']}/{row['arm']}"
        summary = workflow.setdefault(
            key,
            {
                "trials": 0,
                "acceptance_passed": 0,
                "verified_success": 0,
                "ready_for_approval": 0,
                "usage_incomplete": 0,
                "provider_interruptions": 0,
            },
        )
        summary["trials"] += 1
        summary["acceptance_passed"] += bool(row["acceptance"]["passed"])
        summary["verified_success"] += bool(row["task_success"])
        summary["ready_for_approval"] += row["status"] == "ready_for_approval"
        summary["usage_incomplete"] += bool(row["error"])
        summary["provider_interruptions"] += provider_interrupted(row)
    result = {
        "paired": paired,
        "workflow": workflow,
        "failures": failures,
        "note": "Task families overlap and repeats share specifications; these descriptive differences are not independent-sample significance tests.",
    }
    concurrency = directory / "concurrency.json"
    if concurrency.exists():
        result["concurrency"] = json.loads(concurrency.read_text("utf-8"))
    atomic_write(directory / "analysis.json", canonical(result))
    lines = [
        "# Paired benchmark analysis",
        "",
        "| Comparison | Paired trials | Improved | Regressed | Difference |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, value in paired.items():
        lines.append(
            f"| {name} | {value['paired_trials']} | {value['improved']} | {value['regressed']} | {value['difference_percentage_points']:+.1f} pp |"
        )
    lines += [
        "",
        result["note"],
        "",
        "## Workflow outcomes",
        "",
        "| Split / arm | Trials | Acceptance passed | Verified success | Ready for approval | Usage potentially incomplete |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, counts in workflow.items():
        lines.append(
            f"| {name} | {counts['trials']} | {counts['acceptance_passed']} | {counts['verified_success']} | {counts['ready_for_approval']} | {counts['usage_incomplete']} |"
        )
    if "concurrency" in result:
        note = result["concurrency"].get("note")
        if not note and result["concurrency"].get("workflow_wall_times_descriptive_not_isolated"):
            note = "Workflow timing is descriptive, not isolated; local monitoring and checks overlapped some trials."
        if note:
            lines += ["", note, ""]
    lines += [
        "",
        "Observed tokens are a lower bound when a model process fails before reporting turn usage. A zero recorded value on a timeout is not zero actual cost. Passing acceptance and visible checks can still leave reviewer findings requiring attention; approval readiness is reported separately.",
        "",
        "## Failures",
        "",
    ]
    interrupted = sum(provider_interrupted(r) for r in rows)
    if interrupted:
        lines += [
            f"{interrupted} trials include provider quota/rate-limit interruptions. Raw operational scores are retained; do not interpret those interruptions as clean model-capability failures.",
            "",
        ]
    for row in failures:
        lines.append(
            f"- {row['split']}/{row['arm']}/{row['task']} trial {row['repeat']}: groups {row['failed_groups']}; state {row['status']}; error {row['runtime_error']}; run `{row['run_id']}`."
        )
    atomic_write(directory / "ANALYSIS.md", "\n".join(lines).encode())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    print(json.dumps(analyze(parser.parse_args().directory), indent=2))
