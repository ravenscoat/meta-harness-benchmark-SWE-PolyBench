"""Copy completed search-only traces into a new campaign's prior history."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def seed(source, target, all_search=False):
    destination = target / "search-history" / "prior-repairs"
    if destination.exists() or (target / "campaign.json").exists():
        raise ValueError("warm-start requires a new campaign directory")
    report = json.loads((source / "report.json").read_text("utf-8"))
    rows = [
        r
        for r in report["rows"]
        if r["split"] == "search" and (all_search or r["arm"] in {"single", "full"})
    ]
    copied = []
    for row in rows:
        name = f"{row['arm']}-{row['case']}-{row['repeat']}"
        trial = source / "search-history" / name
        score = trial / "score.json"
        sealed = json.loads(score.read_text("utf-8"))
        if sealed != row:
            raise ValueError(f"score mismatch: {name}")
        shutil.copytree(
            trial,
            destination / name,
            ignore=shutil.ignore_patterns("node_modules", "dist", "tmp", "*.sqlite3*", ".git"),
        )
        copied.append(
            {"trial": name, "score_sha256": hashlib.sha256(score.read_bytes()).hexdigest()}
        )
    target.mkdir(parents=True, exist_ok=True)
    (target / "warm-start.json").write_text(
        json.dumps(
            {
                "source": str(source.resolve()),
                "trials": copied,
                "arm_selection": "all_search" if all_search else "baselines_only",
                "note": "Completed search history only; no reserved results or private evaluators. Execution overlap, if any, is recorded separately in concurrency provenance.",
            },
            indent=2,
        ),
        "utf-8",
    )
    print(f"Copied {len(copied)} search trials")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--all-search", action="store_true")
    args = parser.parse_args()
    seed(args.source, args.target, args.all_search)
