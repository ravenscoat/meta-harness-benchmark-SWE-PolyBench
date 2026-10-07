"""Feature additions must earn the same execution evidence as bug repairs."""
from types import SimpleNamespace

import pytest

from benchmarks.polybench.contract_coverage import CoverageSummary, evidence_plan
from benchmarks.polybench.engine import BASE_POLICY, PolyEngine, VisibleVerifier
from hx.models import Check, Settings


def test_feature_schema_requires_executed_requirement_bindings():
    task = SimpleNamespace(kind='feature', report='Add a switch to hide a badge.')
    assert PolyEngine._implementation_contract(None, task) is CoverageSummary
    schema = CoverageSummary.model_json_schema()
    assert set(schema['required']) == set(schema['properties'])
    summary = CoverageSummary(summary='Implemented the requested switch', tests_added=[],
        limitations=[], verification_commands=[['pytest', '-vv']], contract_cases=[])
    assert PolyEngine._candidate_metadata(None, task, summary) == {
        'public_contract': evidence_plan(task.report, [])}


@pytest.mark.parametrize('base_failed', [False, True])
def test_feature_requires_base_failure_even_when_candidate_and_mapping_pass(
    monkeypatch, tmp_path, base_failed
):
    from benchmarks.polybench import engine as module
    from hx.models import Candidate
    removed = []
    container = SimpleNamespace(id='fixture', remove=lambda **kwargs: removed.append(True))
    monkeypatch.setattr(module, 'create', lambda *a, **kw: (container, '/testbed'))
    monkeypatch.setattr(module, 'populate', lambda *a: None)
    monkeypatch.setattr(module, 'assert_clean', lambda *a: None)
    monkeypatch.setattr(module, 'build_check', lambda *a: None)
    monkeypatch.setattr(module, 'command_check', lambda name, *a: Check(
        name=name, passed=True, evidence='actual fixture candidate pass'))
    calls = []
    def regression(*args):
        calls.append('original_source')
        return Check(name='public_regression_reproduced', passed=base_failed,
            evidence='behavior absent on base' if base_failed else 'base also passed')
    monkeypatch.setattr(module, 'regression_check', regression)
    monkeypatch.setattr(module, 'coverage_check', lambda *a: Check(
        name='public_contract_coverage', passed=True, evidence='fixture named witness'))
    candidate = Candidate(base_commit='a', input_commit='a', candidate_commit='b',
        workspace=str(tmp_path), changed_files=['app.js'], diff_sha256='hash',
        verification_commands=[['pytest', '-vv']])
    task = SimpleNamespace(kind='feature', report='Add a visible switch.', base_commit='a')
    result = VisibleVerifier(Settings(), None, {}).run(
        candidate, task, tmp_path, lambda: None, lambda *a: None)
    assert result.passed is base_failed
    assert calls == ['original_source']
    assert len(removed) == 1
    assert {c.name for c in result.checks} >= {
        'public_regression_reproduced', 'public_contract_coverage'}


def test_feature_worker_gets_inventory_and_matching_evidence_contract(monkeypatch, tmp_path):
    from hx.engine import Engine
    engine = object.__new__(PolyEngine)
    engine.adapter = SimpleNamespace()
    engine.case = {'repo': 'fixture', 'language': 'TypeScript'}
    engine.policy = BASE_POLICY
    task = SimpleNamespace(kind='feature', report='Add a switch to hide a badge.')
    monkeypatch.setattr(Engine, '_worker', lambda self, run, step, role, task,
        workspace, context, contract, directory, deadline: context)
    context = engine._worker('run', 'implement', 'implementer', task, tmp_path,
        {}, CoverageSummary, tmp_path, 100)
    assert context['public_contract_inventory']['requirements']
    assert 'Return contract_cases' in context['public_contract_evidence_rules']
    assert 'bug AND feature' in context['verification_contract']
