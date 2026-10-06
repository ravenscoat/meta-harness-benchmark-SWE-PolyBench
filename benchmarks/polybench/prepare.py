from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from hx.store import atomic_write

DATASET_REVISION = "b3fca77b637379f0c01ad86d18753a7ac1998b53"
EVALUATOR_REVISION = "9c836c5d7f3cb991934132b77d29e6941d912a07"
SEED = "hx-polybench-repository-transfer-v1"
REPOSITORIES = {
    "setup": {"yt-dlp/yt-dlp": 1, "mrdoob/three.js": 2,
              "tailwindlabs/tailwindcss": 2},
    "development": {"keras-team/keras": 4, "prettier/prettier": 3,
                    "microsoft/vscode": 3},
    "evaluation": {"huggingface/transformers": 3, "langchain-ai/langchain": 3,
                   "sveltejs/svelte": 3, "serverless/serverless": 3,
                   "mui/material-ui": 8},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value):
    atomic_write(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def read_rows(path: Path):
    csv.field_size_limit(10_000_000)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def select(rows):
    """Selection uses public metadata only, never patches or observed outcomes."""
    selected = []
    for split, repos in REPOSITORIES.items():
        for repo, count in repos.items():
            eligible = [r for r in rows if r["repo"] == repo
                        and r["task_category"] in {"Bug Fix", "Feature"}
                        and 10 <= len(r["problem_statement"]) <= 11500]
            eligible.sort(key=lambda r: hashlib.sha256(
                (SEED + r["instance_id"]).encode()).hexdigest())
            if len(eligible) < count:
                raise ValueError(f"insufficient eligible tasks for {repo}: {len(eligible)}")
            for row in eligible[:count]:
                selected.append({"split": split, "id": row["instance_id"],
                    "repo": repo, "language": row["language"],
                    "category": row["task_category"], "upstream_base": row["base_commit"]})
    return selected


def prepare(root: Path):
    manifest = root / "selection.json"
    if manifest.exists():
        raise ValueError("selection already frozen; use its existing manifest")
    rows = read_rows(root / "dataset.csv")
    cases = select(rows)
    value = {"dataset": "AmazonScience/SWE-PolyBench_Verified",
        "dataset_revision": DATASET_REVISION, "dataset_sha256": sha(root / "dataset.csv"),
        "evaluator_revision": EVALUATOR_REVISION, "seed": SEED,
        "selection_rule": "Fixed repository allocation; hash rank; bugs/features; issue length <=11500. No outcome filtering or replacement.",
        "cases": cases, "planned": {"setup": 5, "development": 10, "evaluation": 20}}
    write(manifest, value)
    by_id = {r["instance_id"]: r for r in rows}
    for case in cases:
        row = by_id[case["id"]]
        write(root / "public" / (case["id"] + ".json"), {
            **case, "problem_statement": row["problem_statement"]})
    print(json.dumps({"selected": len(cases), "splits": value["planned"],
                      "languages": sorted({r["language"] for r in cases})}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    prepare(parser.parse_args().root)
