import pytest

from scripts.run_lean_repaired_three import check_headroom, reject_consumed_parent


@pytest.mark.parametrize('name', ['score.json', 'state/native-state.json'])
def test_recovery_refuses_scored_or_interrupted_identity(tmp_path, name):
    path = tmp_path / 'experiments/heldout-results/lean-case-1' / name
    path.parent.mkdir(parents=True)
    path.write_text('{}')
    with pytest.raises(RuntimeError, match='consumed'):
        reject_consumed_parent(tmp_path)


def test_recovery_preserves_expired_parent_envelope(tmp_path):
    reject_consumed_parent(tmp_path)
    with pytest.raises(RuntimeError, match='headroom'):
        check_headroom(0, 14401, {'deadline': 14400, 'max_reported_tokens': 1500000}, True)
