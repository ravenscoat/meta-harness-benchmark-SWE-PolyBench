"""Public-only diagnostics for a saved MUI candidate; no model or scorer rerun."""
import hashlib
import json
from pathlib import Path

from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.models import Candidate, Task


def main():
    import docker

    root = Path(".hx/absolute-test-runner-repair-v1").resolve()
    old = Path(".hx/one-react-evaluation-v2")
    key = "mui__material-ui-23229"
    case = json.loads((old / "images.json").read_text())[key]
    trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
    score = json.loads((trial / "score.json").read_text())
    candidate = Candidate.model_validate_json((trial / "state/runs" / score["run_id"] /
        "artifacts/implement.json").read_text())
    historical = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    sources = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in Path("benchmarks/polybench").glob("*.py")}
    write(root / "plan.json", {"classification": "Consumed-task public diagnostic, not a new benchmark score",
        "model_calls": 0, "private_grader_access": False, "case": key,
        "candidate_commit": candidate.candidate_commit,
        "original_score_sha256": historical[str((trial / "score.json").resolve())],
        "historical_scores": historical, "source_sha256": sources,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "repair": "Same supported package-manager basename gets same Mocha lifecycle handling for absolute paths"})
    task = Task(id=key, repo=case["repo_path"], report="Saved candidate public command diagnostic.",
        base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
    client = docker.from_env(timeout=1800)
    verifier = VisibleVerifier(load_settings(old / "settings.toml"), client, case)
    results = {}
    try:
        for name, commands in (("original_plan", candidate.verification_commands),
                ("broader_public_suite", [[candidate.verification_commands[0][0], "test:unit", "--grep", "Autocomplete"]])):
            events = []
            def emit(event, data, events=events):
                events.append({"event": event, **data})
            revised = candidate.model_copy(update={"verification_commands": commands})
            verification = verifier.run(revised, task, root / name, lambda: None, emit)
            write(root / name / "verification.json", verification.model_dump())
            write(root / name / "events.json", events)
            results[name] = {"passed": verification.passed, "commands": commands,
                "candidate_commit": candidate.candidate_commit,
                "adaptations": [e for e in events if e["event"] == "tool.public_test_command_adapted"]}
            write(root / "results.json", results)
            print(json.dumps({"event": "diagnostic.finished", "name": name, **results[name]}), flush=True)
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in historical.items())
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in sources.items())
        write(root / "complete.json", {"historical_scores_unchanged": len(historical),
            "model_calls": 0, "official_score_replaced": False, "runtime_unchanged_during_replay": True})
    finally:
        client.close()


if __name__ == "__main__":
    main()
