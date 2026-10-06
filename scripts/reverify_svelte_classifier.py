"""Reverify the unchanged Svelte candidate with no models or official regrade."""
import argparse
import json
import shutil
import time
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import sha, write
from hx.git import validate_candidate
from hx.models import Candidate, Handoff, Task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    old = Path(".hx/worker-environment-development-v2").resolve()
    directory = old / "experiments/search-history/full-sveltejs__svelte-728-1"
    score_path = directory / "score.json"
    score = json.loads(score_path.read_text())
    run_dir = directory / "state/runs" / score["run_id"]
    candidate_path = run_dir / "artifacts/implement.json"
    events_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    expected = next(e["data"]["sha256"] for e in events
        if e["type"] == "step.completed" and e["step_id"] == "implement")
    if sha(candidate_path) != expected:
        raise RuntimeError("Original candidate artifact changed")
    snapshots = sorted((directory / "state").glob("console-snapshot.*.json"))
    original_run = next(r["run"] for r in json.loads(snapshots[-1].read_text())
        if r["run"]["id"] == score["run_id"])
    candidate = Candidate.model_validate_json(candidate_path.read_text())
    task = Task.model_validate(original_run["task"])
    validate_candidate(candidate, task)
    if score["acceptance"]["candidate_commit"] != candidate.candidate_commit:
        raise RuntimeError("Official score references a different candidate")
    _, images, client, settings = runner.resources(old)
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    inputs = {str(p): sha(p) for p in (score_path, candidate_path, events_path,
        old / "batch-plan.json", old / "audit.json", old / "settings.toml")}
    sources = {str(p): sha(p) for folder in (Path("src/hx"), Path("benchmarks/polybench"))
        for p in folder.glob("*.py")}
    sources[str(Path(__file__).resolve())] = sha(Path(__file__))
    write(root / "plan.json", {"type": "model-free verification recovery",
        "runtime": VisibleVerifier.version, "source_run": score["run_id"],
        "candidate_commit": candidate.candidate_commit, "inputs": inputs,
        "sources": sources, "historical_scores": historical, "model_calls": 0,
        "official_regrades": 0})
    write(root / "plan.lock.json", {"sha256": sha(root / "plan.json")})
    shutil.copytree("benchmarks/polybench", root / "runtime-source/benchmarks/polybench",
        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree("src/hx", root / "runtime-source/src/hx",
        ignore=shutil.ignore_patterns("__pycache__"))
    deadline = time.monotonic() + 600
    def control():
        if time.monotonic() >= deadline:
            raise RuntimeError("Model-free reverification deadline exceeded")
    recorded = []
    def emit(kind, data):
        recorded.append({"kind": kind, "data": data})
        write(root / "events.json", recorded)
    verification = VisibleVerifier(settings, client, images[score["case"]]).run(
        candidate, task, root / "verification", control, emit)
    validate_candidate(candidate, task)
    write(root / "verification.json", verification.model_dump())
    handoff = Handoff(run_id="recovery-" + score["run_id"], candidate_commit=candidate.candidate_commit,
        verified=verification.passed, reviewed=False, status="ready_for_approval" if verification.passed else "needs_attention",
        revisions_used=0, blocking_findings=[], known_gaps=verification.known_gaps,
        review_steps=[])
    write(root / "handoff.json", handoff.model_dump())
    for name, expected in {**historical, **inputs, **sources}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError("Sealed evidence/source changed: " + name)
    report = {"runtime": VisibleVerifier.version, "source_run_id": score["run_id"],
        "original_score_sha256": sha(score_path), "candidate_commit": candidate.candidate_commit,
        "original_status": score["status"], "recovery_status": handoff.status,
        "public_verification_passed": verification.passed, "model_calls": 0,
        "official_regrades": 0, "original_official_resolution": score["official_resolved"],
        "historical_score_files_unchanged": len(historical), "source_locks_valid": True,
        "limitation": "New verification recovery only; original benchmark outcome and attention flag preserved. No new coding or official benchmark trial."}
    write(root / "report.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
