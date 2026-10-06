"""Public-only validation of the new gate on preserved coding candidates."""
import hashlib
import json
import time
from pathlib import Path

from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.models import Candidate, Task


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def saved(root, key, run):
    trial = root / "experiments/heldout-results" / ("full-" + key + "-1")
    return Candidate.model_validate_json((trial / "state/runs" / run / "artifacts/implement.json").read_text())


def main():
    import docker

    root = Path(".hx/regression-replay-runtime-v1/probes").resolve()
    if root.exists():
        raise RuntimeError("Probe identity exists; preserve its evidence")
    lang = Path(".hx/harness-repair-evaluation-v1")
    mui = Path(".hx/one-react-evaluation-v2")
    key_l, key_m = "langchain-ai__langchain-6765", "mui__material-ui-23229"
    fixed = Candidate.model_validate_json(Path(
        ".hx/react-contract-reference-analysis-v2/compatibility-fixture-correction/green-candidate.json").read_text())
    cases = [
        ("langchain_saved_pass", lang, key_l, saved(lang, key_l, "r-3026f05168ed4163"), True),
        ("react_corrected", mui, key_m, fixed, True),
        ("react_original_worker", mui, key_m, saved(mui, key_m, "r-9a5c14fc90a64e9f"), False),
    ]
    sources = {str(p): sha(p) for p in Path("benchmarks/polybench").glob("*.py")}
    old = json.loads(Path(".hx/regression-replay-runtime-v1/plan.json").read_text())
    write(root / "freeze.json", {"classification": "Public development diagnostics; no new benchmark scores",
        "runtime_version": VisibleVerifier.version, "source_sha256": sources,
        "script_sha256": sha(Path(__file__)), "model_calls": 0, "private_grader_access": False,
        "cases": [{"name": name, "candidate_commit": c.candidate_commit, "expected_gate_pass": expect}
            for name, _, _, c, expect in cases]})
    (root / "executed-helper.py").write_bytes(Path(__file__).read_bytes())
    client = docker.from_env(timeout=1800)
    results = {}
    try:
        for name, source, key, candidate, expected in cases:
            events = []
            case = json.loads((source / "images.json").read_text())[key]
            task = Task(id=key, repo=case["repo_path"], report="Saved public regression gate diagnostic.",
                base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
            verifier = VisibleVerifier(load_settings(source / "settings.toml"), client, case)
            started = time.monotonic()
            result = verifier.run(candidate, task, root / name, lambda: None,
                lambda event, data, events=events: events.append({"event": event, **data}))
            write(root / name / "verification.json", result.model_dump())
            write(root / name / "events.json", events)
            results[name] = {"passed": result.passed, "expected": expected,
                "seconds": time.monotonic() - started, "checks": result.model_dump()["checks"]}
            write(root / "results.json", results)
            print(json.dumps({"event": "gate.probe", "name": name, "passed": result.passed,
                "expected": expected}), flush=True)
        assert all(r["passed"] == r["expected"] for r in results.values())
        assert all(sha(Path(p)) == h for p, h in sources.items())
        assert all(sha(Path(p.replace("\\", "/"))) == h for p, h in old["historical_scores"].items())
        write(root / "complete.json", {"historical_scores_unchanged": len(old["historical_scores"]),
            "runtime_unchanged_during_probe": True, "model_calls": 0, "private_grader_access": False,
            "limitation": "These development probes do not measure fresh solve rate or complete issue coverage"})
    finally:
        client.close()


if __name__ == "__main__":
    main()
