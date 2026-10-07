"""New comparison lifecycle checks; no model, Docker or grading calls."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hx.models import HXError
from scripts import run_diagnosis_search as module


def test_windows_archive_paths_compare_to_linux_without_resealing():
    assert module.portable_archive({'prior-public-evidence\\summary.json': 'hash'}) == {
        'prior-public-evidence/summary.json': 'hash'}


@pytest.mark.parametrize('archive', [
    {'../secret': 'hash'}, {'C:\\secret': 'hash'}, {'/secret': 'hash'},
    {'a/b': 'one', 'a\\b': 'two'}])
def test_portable_receipts_reject_unsafe_or_ambiguous_paths(archive):
    with pytest.raises(HXError, match='Unsafe or ambiguous'):
        module.portable_archive(archive)


def test_prior_evidence_is_context_not_comparison_scores(tmp_path):
    source = tmp_path / 'sealed-public'
    source.mkdir()
    (source / 'diagnosis-prior.json').write_text(json.dumps({'case': 'dev', 'official_resolved': False}))
    archive = tmp_path / 'development'
    archive.mkdir()
    module.import_prior_public(archive, source)
    assert json.loads((archive / 'prior-public-evidence/diagnosis-prior.json').read_text())['case'] == 'dev'
    assert not list(archive.glob('*/case-*-repeat-*/score.json'))


def test_release_only_other_recorded_images_before_pinning(monkeypatch, tmp_path):
    backend = object.__new__(module.DiagnosedBackend)
    backend.prepared, backend.root = tmp_path / 'prepared', tmp_path
    client = SimpleNamespace(close=lambda: None)
    images = {'current': {'image_id': 'fixed-current'}, 'other': {'image_id': 'fixed-other'}}
    monkeypatch.setattr(module.runner, 'resources', lambda root: (None, images, client, None))
    calls = []
    monkeypatch.setattr(module, 'release_images', lambda c, records: calls.append(('release', records)) or [])
    monkeypatch.setattr(module.runner, 'ensure_image', lambda c, root, pin: calls.append(('pin', pin)))
    backend.retain('current')
    assert calls == [('release', [images['other']]), ('pin', images['current'])]


def test_worker_failure_releases_image_and_preserves_error(monkeypatch, tmp_path):
    backend = object.__new__(module.DiagnosedBackend)
    backend.root, backend.seeded, backend.active = tmp_path, True, False
    monkeypatch.setattr(backend, 'admit', lambda plan: None)
    monkeypatch.setattr(backend, 'check_program', lambda source: None)
    monkeypatch.setattr(backend, 'retain', lambda case: None)
    released = []
    monkeypatch.setattr(backend, 'release', lambda case, directory: released.append(case))
    def fail(*args):
        raise HXError('actual worker failure')
    monkeypatch.setattr(module.PolyBenchBackend, 'evaluate', fail)
    with pytest.raises(HXError, match='actual worker failure'):
        backend.evaluate(Path('candidate.py'), 'case', 1, tmp_path / 'development/baseline/case-0-repeat-1',
                         object(), lambda: None)
    assert released == ['case']
    assert not backend.active


def test_one_image_guard_does_not_pull_when_other_image_has_unrelated_use(monkeypatch, tmp_path):
    backend = object.__new__(module.DiagnosedBackend)
    backend.prepared, backend.root = tmp_path / 'prepared', tmp_path
    client = SimpleNamespace(close=lambda: None)
    images = {'current': {'image_id': 'fixed-current'}, 'other': {'image_id': 'fixed-other'}}
    monkeypatch.setattr(module.runner, 'resources', lambda root: (None, images, client, None))
    monkeypatch.setattr(module, 'release_images', lambda *args: [{'status': 'kept', 'reason': 'unrelated references'}])
    monkeypatch.setattr(module.runner, 'ensure_image', lambda *args: pytest.fail('Must preserve working-set guard'))
    with pytest.raises(HXError, match='One-image guard'):
        backend.retain('current')


def test_consumed_root_cannot_start_helpers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.hx').mkdir()
    consumed = tmp_path / 'consumed'
    consumed.mkdir()
    monkeypatch.setattr(module, 'prepare', lambda *args: pytest.fail('No preparation on consumed root'))
    with pytest.raises(HXError, match='cannot restart'):
        module.run(consumed)
