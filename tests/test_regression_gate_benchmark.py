import json
from pathlib import Path

import pytest

from scripts import run_regression_gate_benchmark as batch


def cases():
    return [{"id": "feature", "split": "evaluation", "category": "Feature"},
            {"id": "dev", "split": "development", "category": "Bug Fix"},
            *[{"id": name, "split": "evaluation", "category": "Bug Fix"}
              for name in ("scored", "exposed", "interrupted", "unused", "later")]]


def test_selection_excludes_scored_exposed_and_interrupted_without_result_filtering():
    state = Path(".hx/old/experiments/heldout-results/full-interrupted-1/state/native-state.json")
    assert batch.select_case(cases(), {"scored", "exposed"}, [state])["id"] == "unused"


def test_no_replacement_when_all_bug_identities_consumed():
    with pytest.raises(RuntimeError, match="No unused"):
        batch.select_case(cases(), {c["id"] for c in cases()}, [])


def test_inventory_includes_failed_scores_exposures_and_unscored_states(tmp_path):
    root = tmp_path / ".hx"
    trial = root / "old/experiments/heldout-results/full-scored-1"
    trial.mkdir(parents=True)
    (trial / "score.json").write_text(json.dumps({"case": "scored", "official_resolved": False}))
    (root / "old/exposure.json").write_text(json.dumps({"cases": ["exposed"]}))
    state = root / "old/experiments/heldout-results/full-interrupted-1/state"
    state.mkdir(parents=True)
    (state / "native-state.json").write_text("{}")
    scores, exposures, used, states = batch.inventory(root)
    assert len(scores) == len(exposures) == len(states) == 1
    assert used == {"scored", "exposed"}
    assert batch.select_case(cases(), used, states)["id"] == "unused"
