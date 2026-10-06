"""Replay saved candidates after delivery/cache fixes; diagnostics, not new scores."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.grader import grade, register_vendor
from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.prepare import read_rows, write
from benchmarks.polybench.runner import VENDOR
from hx.config import load_settings
from hx.models import Candidate, Task


def main(root):
    import docker
    root.mkdir(parents=True, exist_ok=False)
    old = Path(".hx/paper-polybench-v1")
    images = json.loads((old / "images.json").read_text())
    rows = {r["instance_id"]: r for r in read_rows(old / "dataset.csv")}
    # Consume only exposed tasks and saved source; no model calls or hidden context.
    write(root / "images.json", images)
    (root / "storage.json").write_bytes((old / "storage.json").read_bytes())
    historical = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    write(root / "plan.json", {"classification": "Consumed-task diagnostics; original scores retained",
        "model_calls": 0, "cases": list(reversed(images)), "historical_scores": historical,
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("benchmarks/polybench").glob("*.py")}})
    register_vendor(VENDOR.resolve())
    client = docker.from_env(timeout=1800)
    settings = load_settings(old / "settings.toml")
    results = []
    for key in reversed(images):
        started = time.monotonic()
        case = images[key]
        print(json.dumps({"event": "diagnostic.started", "case": key}), flush=True)
        ensure_image(client, root, case)
        trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
        score = json.loads((trial / "score.json").read_text())
        artifacts = trial / "state/runs" / score["run_id"] / "artifacts"
        artifact = artifacts / ("revise_1.json" if (artifacts / "revise_1.json").exists() else "implement.json")
        candidate = Candidate.model_validate_json(artifact.read_text())
        directory = root / key
        directory.mkdir()
        patch, delivery = production_patch(candidate)
        (directory / "production.patch").write_bytes(patch.encode())
        write(directory / "delivery.json", delivery)
        task = Task(id=key, repo=case["repo_path"], report="Replay public verification on saved candidate.",
                    base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
        def emit(name, data, key=key):
            print(json.dumps({"event": name, "case": key, **data}), flush=True)
        verification = VisibleVerifier(settings, client, case).run(candidate, task,
            directory / "public-replay", lambda: None, emit)
        write(directory / "verification.json", verification.model_dump())
        accepted = grade(rows[key], patch, directory / "private-official-diagnostic", client)
        outcome = {"case": key, "public_passed": verification.passed,
            "official_diagnostic_resolved": accepted["resolved"],
            "patch_rejected": bool(accepted["candidate_patch_error"]),
            "grader_error": accepted["infrastructure_error"],
            "required_tests_unobserved": len(accepted["expected_tests_unobserved"]),
            "wall_seconds": time.monotonic() - started, "model_tokens": 0,
            "classification": "Saved candidate, changed delivery/environment; not a fresh benchmark result"}
        results.append(outcome)
        write(root / "results.json", results)
        print(json.dumps(outcome), flush=True)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in historical.items())
    write(root / "complete.json", {"historical_scores_unchanged": len(historical), "model_calls": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    main(parser.parse_args().root.resolve())
