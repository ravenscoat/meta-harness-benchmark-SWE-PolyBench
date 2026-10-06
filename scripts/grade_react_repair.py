"""One official development diagnostic after the public React repair is frozen.

The consumed task stays development-only. No model or reference-patch access;
private evaluator inputs are confined to the existing official grader.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.grader import grade, register_vendor
from benchmarks.polybench.prepare import read_rows, write
from hx.git import assert_clean
from hx.models import Candidate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(public_root=None, output_root=None):
    import docker

    root = Path(output_root or ".hx/react-contract-official-diagnostic-v1").resolve()
    if root.exists():
        raise RuntimeError("Identity exists; never replace a diagnostic outcome.")
    public = Path(public_root or ".hx/react-contract-repair-v1").resolve()
    old = Path(".hx/one-react-evaluation-v2").resolve()
    key = "mui__material-ui-23229"
    complete = json.loads((public / "complete.json").read_text())
    candidate = Candidate.model_validate_json((public / "green-candidate.json").read_text())
    assert_clean(Path(candidate.workspace), candidate.candidate_commit)
    patch, delivery = production_patch(candidate)
    assert hashlib.sha256(patch.encode()).hexdigest() == complete["production_patch_sha256"]
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    case = json.loads((old / "images.json").read_text())[key]
    vendor = Path(".hx/vendor/SWE-PolyBench-9c836c5d").resolve()
    selection = json.loads((old / "selection.json").read_text())
    assert sha(old / "dataset.csv") == selection["dataset_sha256"]
    write(root / "freeze.json", {"classification": "Consumed-case development diagnostic, not heldout",
        "model_calls": 0, "candidate_commit": candidate.candidate_commit,
        "public_proof_sha256": sha(public / "complete.json"),
        "production_patch_sha256": complete["production_patch_sha256"],
        "delivery": delivery, "dataset_sha256": selection["dataset_sha256"],
        "script_sha256": sha(Path(__file__)), "historical_scores": historical,
        "public_reference_informed": bool(complete.get("reference_informed", False)),
        "private_reference_patch_access": False, "private_inputs": "Existing official grader only",
        "constraint": "No further code tuning in this identity based on official feedback"})
    (root / "executed-helper.py").write_bytes(Path(__file__).read_bytes())
    register_vendor(vendor)
    row = next(r for r in read_rows(old / "dataset.csv") if r["instance_id"] == key)
    client = docker.from_env(timeout=1800)
    started = time.monotonic()
    try:
        alias = "polybench_" + row["language"].lower() + "_" + key.lower()
        assert client.images.get(alias).id == case["image_id"]
        result = grade(row, patch, root / "private-evaluation", client)
        aggregate = {"classification": "Development diagnostic; original score retained",
            "case": key, "official_resolved": result["resolved"],
            "required_tests_unobserved": len(result["expected_tests_unobserved"]),
            "observed_passed": len(result["passed_tests"]),
            "observed_failed": len(result["failed_tests"]),
            "infrastructure_error": result["infrastructure_error"],
            "candidate_patch_error": result["candidate_patch_error"],
            "seconds": time.monotonic() - started, "model_calls": 0,
            "candidate_commit": candidate.candidate_commit,
            "private_score_sha256": sha(root / "private-evaluation/score.json")}
        write(root / "aggregate.json", aggregate)
        assert all(sha(Path(p)) == h for p, h in historical.items())
        assert_clean(Path(candidate.workspace), candidate.candidate_commit)
        write(root / "complete.json", {"historical_scores_unchanged": len(historical),
            "original_score_replaced": False, "candidate_unchanged_after_freeze": True})
        print(json.dumps(aggregate), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    arguments = parser.parse_args()
    main(arguments.public_root, arguments.output_root)
