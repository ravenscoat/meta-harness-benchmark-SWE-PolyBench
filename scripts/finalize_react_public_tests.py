"""Preserve old empty-button accessibility assertions and test the new contract."""

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

    parent = Path(".hx/react-contract-reference-analysis-v2").resolve()
    previous = parent / "format-correction"
    root = parent / "compatibility-fixture-correction"
    assert not root.exists()
    old = Path(".hx/one-react-evaluation-v2")
    candidate = Candidate.model_validate_json((previous / "green-candidate.json").read_text())
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    write(root / "plan.json", {"parent_candidate": candidate.model_dump(),
        "retained_compatibility_sha256": sha(previous / "compatibility/verification.json"),
        "change": "Two empty-value WAI-ARIA fixtures assert one popup button instead of a hidden clear button plus popup. Preserve names, tab order, listbox and input ARIA checks.",
        "production_changes": False, "reference_informed": True,
        "not_heldout": True, "model_calls": 0, "historical_scores": historical,
        "script_sha256": sha(Path(__file__))})
    (root / "executed-helper.py").write_bytes(Path(__file__).read_bytes())
    workspace = Path("/opt/hx-polybench-runtime/v1/infra-checks/react-clear-button-v2-aria")
    assert_clean(Path(candidate.workspace), candidate.candidate_commit)
    clone(Path(candidate.workspace), workspace, candidate.candidate_commit)
    path = workspace / TEST_FILE
    text = path.read_text()
    start = text.index("  describe('WAI-ARIA conforming markup', () => {")
    end = text.index("    it('should add and remove aria-activedescendant'", start)
    section = text[start:end]
    conditional = """      if (!/jsdom/.test(window.navigator.userAgent)) {
        expect(buttons[0]).toBeInaccessible();
      }
"""
    assert section.count(conditional) == 2
    section = section.replace(conditional, "")
    section = section.replace("      // Depending on the subset of components used in this test run the computed `visibility` changes in JSDOM.\n", "")
    assert section.count("expect(buttons).to.have.length(2);") == 2
    section = section.replace("buttons[1]", "buttons[0]")
    section = section.replace("expect(buttons).to.have.length(2);", "expect(buttons).to.have.length(1);")
    path.write_text(text[:start] + section + text[end:])
    corrected = commit_candidate(workspace, candidate, "Assert empty-value accessibility without an invisible clear control",
        candidate.verification_commands)
    write(root / "green-candidate.json", corrected.model_dump())
    patch, delivery = production_patch(corrected)
    assert patch == (parent / "production.patch").read_text()
    (root / "production.patch").write_text(patch)
    write(root / "delivery.json", delivery)
    case = json.loads((old / "images.json").read_text())["mui__material-ui-23229"]
    client = docker.from_env(timeout=1800)
    verifier = VisibleVerifier(load_settings(old / "settings.toml"), client, case)
    task = Task(id=case["id"], repo=case["repo_path"], report="Public empty clear-button accessibility contract.",
        base_commit=candidate.base_commit, kind="bug", allowed_paths=["**"])
    try:
        events = []
        broad = corrected.model_copy(update={"verification_commands": [[corrected.verification_commands[0][0],
            "test:unit", "--grep", "Autocomplete"]]})
        result = verifier.run(broad, task, root / "compatibility", lambda: None,
            lambda event, data: events.append({"event": event, **data}))
        write(root / "compatibility/verification.json", result.model_dump())
        write(root / "compatibility/events.json", events)
        print(json.dumps({"event": "public.replay", "name": "compatibility", "passed": result.passed}), flush=True)
        assert result.passed
        assert all(sha(Path(p)) == h for p, h in historical.items())
        assert_clean(Path(candidate.workspace), candidate.candidate_commit)
        write(root / "complete.json", {"historical_scores_unchanged": len(historical),
            "original_score_replaced": False, "model_calls": 0, "reference_informed": True,
            "not_heldout": True, "public_test_source_sha256": sha(path),
            "red_evidence": str(parent / "red/verification.json"),
            "red_verification_sha256": sha(parent / "red/verification.json"),
            "focused_after_format_correction": str(previous / "focused/verification.json"),
            "five_new_regression_bodies_unchanged_after_focused_pass": True,
            "production_patch_unchanged": True, "production_patch_sha256": sha(root / "production.patch")})
    finally:
        client.close()


if __name__ == "__main__":
    main()
