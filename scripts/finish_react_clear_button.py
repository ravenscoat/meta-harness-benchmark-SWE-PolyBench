"""Preserve v2's whitespace failure and validate a separately committed correction."""

import json
from pathlib import Path

from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.prepare import write
from hx.config import load_settings
from hx.git import assert_clean, clone
from hx.models import Candidate, Task
from scripts.repair_react_contract import TEST_FILE, commit_candidate, sha


def main():
    import docker

    old = Path(".hx/one-react-evaluation-v2")
    parent = Path(".hx/react-contract-reference-analysis-v2").resolve()
    root = parent / "format-correction"
    assert not root.exists()
    candidate = Candidate.model_validate_json((parent / "green-candidate.json").read_text())
    previous = json.loads((parent / "green/verification.json").read_text())
    assert not previous["passed"]
    assert previous["checks"][0]["name"] == "patch_whitespace"
    assert not previous["checks"][0]["passed"] and previous["checks"][1]["passed"]
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    assert_clean(Path(candidate.workspace), candidate.candidate_commit)
    workspace = Path("/opt/hx-polybench-runtime/v1/infra-checks/react-clear-button-v2-format")
    write(root / "plan.json", {"parent_candidate": candidate.model_dump(),
        "retained_verification": str(parent / "green/verification.json"),
        "retained_verification_sha256": sha(parent / "green/verification.json"),
        "reason": "Helper left two spaces on a blank line while removing the worker's misleading regression",
        "change": "Strip trailing whitespace from test source only; production patch must remain byte-identical",
        "reference_informed": True, "not_heldout": True, "model_calls": 0,
        "script_sha256": sha(Path(__file__)), "historical_scores": historical})
    (root / "executed-helper.py").write_bytes(Path(__file__).read_bytes())
    clone(Path(candidate.workspace), workspace, candidate.candidate_commit)
    tests = workspace / TEST_FILE
    before = tests.read_text()
    after = "\n".join(line.rstrip() for line in before.splitlines()) + "\n"
    assert after != before
    tests.write_text(after)
    corrected = commit_candidate(workspace, candidate, "Remove diagnostic test trailing whitespace",
        candidate.verification_commands)
    write(root / "green-candidate.json", corrected.model_dump())
    patch, delivery = production_patch(corrected)
    assert patch == (parent / "production.patch").read_text()
    (root / "production.patch").write_text(patch)
    write(root / "delivery.json", delivery)
    case = json.loads((old / "images.json").read_text())["mui__material-ui-23229"]
    task = Task(id=case["id"], repo=case["repo_path"], report="Public clear-button diagnostic completion.",
        base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
    client = docker.from_env(timeout=1800)
    verifier = VisibleVerifier(load_settings(old / "settings.toml"), client, case)
    results = {}
    try:
        for name, commands in (("focused", corrected.verification_commands),
            ("compatibility", [[corrected.verification_commands[0][0], "test:unit", "--grep", "Autocomplete"]])):
            events = []
            result = verifier.run(corrected.model_copy(update={"verification_commands": commands}),
                task, root / name, lambda: None,
                lambda event, data, events=events: events.append({"event": event, **data}))
            write(root / name / "verification.json", result.model_dump())
            write(root / name / "events.json", events)
            results[name] = result.model_dump()
            write(root / "results.json", results)
            print(json.dumps({"event": "public.replay", "name": name, "passed": result.passed}), flush=True)
            assert result.passed
        assert all(sha(Path(p)) == h for p, h in historical.items())
        assert_clean(Path(candidate.workspace), candidate.candidate_commit)
        write(root / "complete.json", {"model_calls": 0,
            "reference_informed": True, "not_heldout": True,
            "historical_scores_unchanged": len(historical), "original_score_replaced": False,
            "red_evidence": str(parent / "red/verification.json"),
            "red_verification_sha256": sha(parent / "red/verification.json"),
            "public_test_source_sha256": sha(tests),
            "formatting_only_difference_after_original_red_green": True,
            "production_patch_unchanged": True,
            "production_patch_sha256": sha(root / "production.patch")})
    finally:
        client.close()


if __name__ == "__main__":
    main()
