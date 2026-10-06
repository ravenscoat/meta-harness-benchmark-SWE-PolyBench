import json
from types import SimpleNamespace

import pytest

from benchmarks.polybench.contract_coverage import (
    LIMITATION,
    ContractCase,
    CoverageSummary,
    coverage_check,
    evidence_plan,
    inventory,
    observed_tests,
)
from hx.models import Candidate, Check

REPORT = """A reproducible length bug.
### Expected behavior
- Clear warning or error when the combined length exceeds the limit.
- Accept the supported prompt normally.
### Other information
Unrelated environment details.
"""


def binding(requirement="r01", scenario="below", name="below"):
    return ContractCase(requirement=requirement, scenario=scenario,
                        test_id="pytest:tests/test_behavior.py::test_" + name,
                        assertion="Assert the described public behavior at this input.")


def candidate(tmp_path, cases):
    return Candidate(base_commit="a", input_commit="a", candidate_commit="b",
        workspace=str(tmp_path), changed_files=["app.py"], diff_sha256="c",
        verification_commands=[["pytest", "-vv", "tests/test_behavior.py"]],
        public_contract=evidence_plan(REPORT, cases))


def logs(tmp_path, names, status="PASSED"):
    target = tmp_path / "public_test_1/stdout.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(f"tests/test_behavior.py::test_{name} {status} [100%]" for name in names))


def verify(tmp_path, cases):
    return coverage_check(candidate(tmp_path, cases), SimpleNamespace(report=REPORT), tmp_path,
                          [Check(name="public_test_1", passed=True, evidence="summary")], lambda *a: None)


def test_public_inventory_preserves_distinct_requirements_and_boundary_scenarios():
    value = inventory(REPORT)
    assert not value["fallback"]
    assert len(value["requirements"]) == 2
    assert value["requirements"][0]["scenarios"] == ["below", "at", "above"]
    assert value["requirements"][1]["scenarios"] == ["behavior"]
    assert "environment" not in str(value)
    assert inventory("Repair ordinary behavior")["fallback"]


def test_expected_section_ignores_code_fences_and_fails_closed_on_overflow():
    report = "# Expected behavior\n- Preserve input.\n```\n- invented requirement\n```\n"
    assert len(inventory(report)["requirements"]) == 1
    assert inventory("# Requirements\n" + "\n".join(f"- Requirement {i}" for i in range(9)))["errors"]


def test_every_output_property_including_nested_cases_is_required():
    schema = CoverageSummary.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    nested = schema["$defs"]["ContractCase"]
    assert set(nested["required"]) == set(nested["properties"])
    assert schema["additionalProperties"] is nested["additionalProperties"] is False


def test_issue_comments_and_single_backtick_code_are_not_requirements():
    report = ('## Expected Behavior 🤔\n<!---\nDescribe what should happen.\n-->\n'
              'Generate unique `Mui` prefixed class names.\n`\n.disabled {\n opacity: 0.5;\n}\n`\n'
              'Keep disabled switches isolated from ListItem styles.\n## Current Behavior\nWrong styles.')
    value = inventory(report)
    assert [r['quote'] for r in value['requirements']] == [
        'Generate unique `Mui` prefixed class names.',
        'Keep disabled switches isolated from ListItem styles.']
    assert not value['errors'] and not value['fallback']


def test_hidden_heading_cannot_activate_or_end_expected_section():
    report = '# Expected behavior\nKeep input.\n<!--\n# Current behavior\nTemplate text\n-->\nKeep output.\n'
    assert [r['quote'] for r in inventory(report)['requirements']] == ['Keep input.', 'Keep output.']
    assert 'hidden' not in inventory('Visible behavior.<!-- hidden template -->')['requirements'][0]['quote']


def test_real_named_passes_cover_all_required_cases(tmp_path):
    logs(tmp_path, ["below", "at", "above", "normal"])
    cases = [binding(scenario=name, name=name) for name in ["below", "at", "above"]]
    cases.append(binding("r02", "behavior", "normal"))
    assert verify(tmp_path, cases).passed
    artifact = json.loads((tmp_path / "contract_coverage.json").read_text())
    assert len(artifact["covered"]) == 4 and artifact["candidate_commit"] == "b"
    assert artifact["limitation"] == LIMITATION


def test_saved_failure_shape_does_not_cover_missing_limit_behavior(tmp_path):
    logs(tmp_path, ["normal"])
    result = verify(tmp_path, [binding("r02", "behavior", "normal")])
    assert not result.passed
    for scenario in ["below", "at", "above"]:
        assert f"Missing r01/{scenario}" in result.evidence


def test_repeating_one_test_across_commands_or_claims_is_not_distinct_evidence(tmp_path):
    logs(tmp_path, ["same", "same"])
    result = verify(tmp_path, [binding(scenario=name, name="same") for name in ["below", "at", "above"]])
    assert not result.passed and "Duplicate evidence" in result.evidence


def test_distinct_extra_witnesses_for_one_obligation_are_allowed(tmp_path):
    report = 'Repair ordinary behavior'
    cases = [binding('r01', 'behavior', name) for name in ['bare', 'foreign', 'updated']]
    logs(tmp_path, ['bare', 'foreign', 'updated'])
    saved = candidate(tmp_path, cases).model_copy(update={'public_contract': evidence_plan(report, cases)})
    result = coverage_check(saved, SimpleNamespace(report=report), tmp_path,
        [Check(name='public_test_1', passed=True, evidence='summary')], lambda *a: None)
    assert result.passed
    artifact = json.loads((tmp_path / 'contract_coverage.json').read_text())
    assert len(artifact['covered']) == 1 and len(artifact['bindings']) == 3


def test_extra_unobserved_witness_still_blocks_existing_coverage(tmp_path):
    report = 'Repair ordinary behavior'
    cases = [binding('r01', 'behavior', name) for name in ['bare', 'missing']]
    logs(tmp_path, ['bare'])
    saved = candidate(tmp_path, cases).model_copy(update={'public_contract': evidence_plan(report, cases)})
    result = coverage_check(saved, SimpleNamespace(report=report), tmp_path,
        [Check(name='public_test_1', passed=True, evidence='summary')], lambda *a: None)
    assert not result.passed and 'Unobserved' in result.evidence


@pytest.mark.parametrize("status", ["SKIPPED", "XFAIL", "XPASS", "ERROR", "FAILED"])
def test_nonpassing_status_cannot_satisfy_claim(tmp_path, status):
    logs(tmp_path, ["below"], status)
    assert "Unobserved passing test" in verify(tmp_path, [binding()]).evidence


def test_summary_counts_and_stale_report_hash_cannot_satisfy_coverage(tmp_path):
    target = tmp_path / "public_test_1/stdout.txt"
    target.parent.mkdir()
    target.write_text("999 passed")
    assert "Unobserved" in verify(tmp_path, [binding()]).evidence
    saved = candidate(tmp_path, [binding()])
    result = coverage_check(saved, SimpleNamespace(report=REPORT + "Changed."), tmp_path, [], lambda *a: None)
    assert "stale" in result.evidence


def test_builtin_javascript_reporters_skip_pending_and_conflicting_tests():
    mocha = json.dumps({"stats": {}, "passes": [{"fullTitle": "component below"}],
                        "pending": [{"fullTitle": "component at"}]})
    jest = json.dumps({"testResults": [{"assertionResults": [
        {"fullName": "component above", "status": "passed"},
        {"fullName": "component pending", "status": "pending"}]}]})
    assert observed_tests(mocha + "\n" + jest) == {"mocha:component below", "js:component above"}
    assert observed_tests("tests/a.py::test_x PASSED\ntests/a.py::test_x FAILED") == set()
    assert observed_tests('{"stats": {}, "passes": [], "failures": null}') == set()


def test_json_reporter_base_failures_remain_behavioral_only_for_assertions():
    from benchmarks.polybench.regression import classify
    mocha = {"stats": {"failures": 1}, "failures": [{"fullTitle": "component boundary",
              "err": {"stack": "AssertionError: expected 1 to equal 2"}}]}
    assert classify(Check(name="base", passed=False, evidence=json.dumps(mocha))) == "behavioral_failure"
    mocha["failures"][0]["fullTitle"] = 'before all hook for component'
    assert classify(Check(name="base", passed=False, evidence=json.dumps(mocha))) != "behavioral_failure"
    mocha["failures"][0]["err"] = {"stack": "Error: fixture unavailable"}
    assert classify(Check(name="base", passed=False, evidence=json.dumps(mocha))) != "behavioral_failure"
    jest = {"testResults": [{"assertionResults": [{"fullName": "boundary", "status": "failed",
             "failureMessages": ["Expected: 2 Received: 1"]}]}]}
    assert classify(Check(name="base", passed=False, evidence=json.dumps(jest))) == "behavioral_failure"


def test_false_mapping_semantics_are_not_claimed_to_be_independently_verified(tmp_path):
    # A worker can misdescribe what assertions mean. Keep that limit explicit;
    # structural coverage must never be advertised as proving full correctness.
    assert "not independent semantic proof" in LIMITATION


def test_public_green_and_base_red_still_block_when_coverage_is_missing(monkeypatch, tmp_path):
    import benchmarks.polybench.engine as module
    from hx.models import Settings
    container = SimpleNamespace(id="public", remove=lambda **kwargs: None)
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/testbed"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "assert_clean", lambda *a: None)
    monkeypatch.setattr(module, "command_check", lambda name, *a: Check(name=name, passed=True, evidence="passed"))
    monkeypatch.setattr(module, "regression_check", lambda *a: Check(name="reproduced", passed=True, evidence="base failed"))
    saved = candidate(tmp_path, [])
    saved.changed_files = ["service.js"]
    task = SimpleNamespace(base_commit="a", report=REPORT, kind="bug")
    result = module.VisibleVerifier(Settings(), None, {}).run(saved, task, tmp_path, lambda: None, lambda *a: None)
    assert not result.passed
    assert next(c for c in result.checks if c.name == "public_contract_coverage").passed is False


def test_metadata_only_revision_preserves_source_and_rejects_unchanged_noop(tmp_path):
    from hx.engine import derive_with_test_plan
    from hx.git import derive, git
    from hx.models import HXError, Task, WorkerSummary
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    (tmp_path / "app.py").write_text("value = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    task = Task(id="contract-test", report="Repair ordinary behavior", repo=str(tmp_path),
                base_commit=base, allowed_paths=["**"], protected_paths=["private/**"])
    (tmp_path / "app.py").write_text("value = 2\n")
    previous = derive(tmp_path, base, base, task).model_copy(update={"verification_commands": [["pytest", "-vv"]]})
    summary = WorkerSummary(summary="Coverage metadata revised", tests_added=[], limitations=[], verification_commands=[["pytest", "-vv"]])
    result = derive_with_test_plan(tmp_path, task, previous.candidate_commit, previous, summary, metadata_changed=True)
    assert result.candidate_commit == previous.candidate_commit
    assert result.diff_sha256 == previous.diff_sha256
    with pytest.raises(HXError, match="no changes"):
        derive_with_test_plan(tmp_path, task, previous.candidate_commit, previous, summary)


def test_missing_coverage_reaches_repair_and_metadata_only_fix_preserves_commit(project, setup_engine):
    from benchmarks.polybench.engine import PolyEngine
    from hx.engine import Engine
    from hx.models import Verification
    from scripts.hx_console import detail
    engine, adapter = setup_engine(workflow="single")
    class ContractEngine(Engine):
        _implementation_contract = PolyEngine._implementation_contract
        _candidate_metadata = PolyEngine._candidate_metadata
    engine = ContractEngine(engine.store, engine.settings.model_copy(update={"max_revisions": 1}), adapter)
    original = adapter.run
    contexts = []
    def scripted(role, task, workspace, context, *args):
        contexts.append(context)
        if len(contexts) == 1:
            result = original(role, task, workspace, context, *args)
            result["verification_commands"] = [["pytest", "-vv", "tests/test_regression.py"]]
            result["contract_cases"] = []
            return result
        # The second fixture call changes only evidence, never source or test code.
        adapter.calls[role] += 1
        cases = [binding(scenario=name, name=name) for name in ["below", "at", "above"]]
        cases.append(binding("r02", "behavior", "normal"))
        return {"summary": "Corrected coverage evidence", "limitations": [], "tests_added": [],
                "verification_commands": [["pytest", "-vv", "tests/test_regression.py"]],
                "contract_cases": [case.model_dump() for case in cases]}
    adapter.run = scripted
    commits = []
    class FixtureVerifier:
        def run(self, candidate, task, directory, control, emit):
            commits.append(candidate.candidate_commit)
            logs(directory, ["below", "at", "above", "normal"])
            check = coverage_check(candidate, task, directory,
                                   [Check(name="public_test_1", passed=True, evidence="fixture")], emit)
            return Verification(candidate_commit=candidate.candidate_commit, passed=check.passed,
                                checks=[check], changed_line_coverage=None, known_gaps=[LIMITATION])
    engine.verifier = FixtureVerifier()
    task = project["missing-task"].model_copy(update={"report": REPORT})
    run = engine.create(task)
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    assert adapter.calls == {"implementer": 2}
    assert len(commits) == 2 and commits[0] == commits[1]
    assert contexts[1]["repair_plan"]["failed_checks"][0]["name"] == "public_contract_coverage"
    assert "Missing r01" in contexts[1]["repair_plan"]["failed_checks"][0]["evidence"]
    artifact = json.loads((engine.store.run_dir(run["id"]) / "artifacts/revise_1.json").read_text())
    assert len(artifact["public_contract"]["cases"]) == 4
    assert "1/4" in detail("verification.contract_coverage", {"passed": False, "covered": 1, "required": 4})
