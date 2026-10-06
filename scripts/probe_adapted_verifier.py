"""Exercise automatic command repair on saved public evidence, without a model."""
import json
from pathlib import Path

from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.models import Candidate, Task


def main():
    import docker
    root = Path(".hx/adapted-public-verifier-v1").resolve()
    root.mkdir(exist_ok=False)
    old = Path(".hx/paper-polybench-v1")
    key = "mui__material-ui-18683"
    case = json.loads((old / "images.json").read_text())[key]
    trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
    score = json.loads((trial / "score.json").read_text())
    # Original unsupported environment-prefix plan, before its expensive Luna repair.
    candidate = Candidate.model_validate_json((trial / "state/runs" / score["run_id"] /
                                               "artifacts/implement.json").read_text())
    task = Task(id=key, repo=case["repo_path"], report="Consumed-task public verifier diagnostic.",
        base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
    events = []
    def emit(name, data):
        events.append({"event": name, **data})
    verification = VisibleVerifier(load_settings(old / "settings.toml"), docker.from_env(timeout=1800), case).run(
        candidate, task, root, lambda: None, emit)
    write(root / "verification.json", verification.model_dump())
    write(root / "events.json", events)
    write(root / "result.json", {"model_calls": 0, "candidate_commit": candidate.candidate_commit,
        "passed": verification.passed, "original_commands": candidate.verification_commands,
        "command_adaptations": [e for e in events if e["event"] == "tool.public_test_command_adapted"]})
    print(json.dumps({"passed": verification.passed, "events": events}), flush=True)


if __name__ == "__main__":
    main()
