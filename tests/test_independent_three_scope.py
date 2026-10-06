import json
from pathlib import Path

import pytest

from scripts.run_independent_three import CASES, prepare


def test_three_distinct_bug_tasks_exclude_reference_guided_repairs():
    assert len(CASES)==len(set(CASES))==3
    assert not set(CASES)&{'huggingface__transformers-26164','mui__material-ui-23229'}


def test_scored_case_cannot_be_presented_as_untouched(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    directory=Path('.hx/old/experiments/heldout-results/trial')
    directory.mkdir(parents=True)
    (directory/'score.json').write_text(json.dumps({'case':CASES[0]}))
    with pytest.raises(RuntimeError,match='already has'):
        prepare(Path('new-batch'))
    assert not Path('new-batch').exists()


def test_unscored_started_identity_also_excluded(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    directory=Path('.hx/old/experiments/heldout-results/trial/state')
    directory.mkdir(parents=True)
    (directory/'console-snapshot.1.json').write_text(json.dumps([{'task':{'id':CASES[0]}}]))
    with pytest.raises(RuntimeError,match='already has'):
        prepare(Path('new-batch'))


def test_declared_repair_reserve_is_supported_and_bounded():
    from hx.models import Settings
    assert Settings(repair_token_reserve=150000).repair_token_reserve==150000
    with pytest.raises(ValueError):
        Settings(repair_token_reserve=200001)
