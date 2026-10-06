"""Explicit public Mocha lifecycle diagnostic; never rewrites scored verification."""
import json
from pathlib import Path

from benchmarks.polybench.containers import create, populate
from benchmarks.polybench.prepare import write
from benchmarks.polybench.test_environment import docker_environment
from hx.models import Candidate
from hx.process import clean_env, execute


def main():
    import docker
    root = Path(".hx/mocha-lifecycle-probe-v1")
    root.mkdir(exist_ok=False)
    old = Path(".hx/paper-polybench-v1")
    key = "mui__material-ui-18683"
    case = json.loads((old / "images.json").read_text())[key]
    trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
    score = json.loads((trial / "score.json").read_text())
    candidate = Candidate.model_validate_json((trial / "state/runs" / score["run_id"] /
                                               "artifacts/revise_1.json").read_text())
    client = docker.from_env(timeout=1800)
    container, workdir = create(client, case, offline=True)
    try:
        populate(container, workdir, Path(candidate.workspace), case)
        argv = ["npm", "run", "test:unit", "--", "--grep", "useMediaQuery", "--exit"]
        write(root / "plan.json", {"model_calls": 0, "case": key,
            "candidate_commit": candidate.candidate_commit, "argv": argv,
            "reason": "Mocha completed 11 assertions but process stayed alive after cache fix",
            "limitation": "Force exit does not establish absence of dangling resource handles"})
        code, out, err = execute(["docker", "exec", "-u", "1000:1000", *docker_environment(),
            "-w", workdir, container.id, *argv], root.resolve(), clean_env(), root / "command",
            180, lambda: None, max_bytes=2000000)
        write(root / "result.json", {"exit_code": code, "stdout": out, "stderr": err})
        print(json.dumps({"exit_code": code, "stdout": out, "stderr": err}), flush=True)
    finally:
        container.remove(force=True)


if __name__ == "__main__":
    main()
