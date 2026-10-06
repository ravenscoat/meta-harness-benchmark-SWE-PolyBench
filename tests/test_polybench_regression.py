import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from benchmarks.polybench.engine import VisibleVerifier
from benchmarks.polybench.regression import LIMITATION, classify, regression_check
from benchmarks.polybench.regression import test_projection as project_tests
from hx.models import Cancelled, Candidate, Check, Settings


@pytest.mark.parametrize("passed,output,expected", [
    (False, "AssertionError: expected false to equal true\n  1 failing\n", "behavioral_failure"),
    (False, "FAILED tests/test_bug.py::test_behavior - AttributeError\n1 failed in 0.1s", "behavioral_failure"),
    (False, "Tests: 1 failed, 2 passed, 3 total\nExpected: 2\nReceived: 1", "behavioral_failure"),
    (False, "# fail 1\ncode: ERR_ASSERTION", "behavioral_failure"),
    (True, "1 passed in 0.1s", "baseline_passed"),
    (True, "  3 passing (1s)", "baseline_passed"),
    (True, "no tests ran in 0.1s", "no_tests"),
    (True, "  0 passing (1s)", "no_tests"),
    (True, "hello", "inconclusive"),
    (False, "AssertionError\n1 failing\nChild tree terminated", "timeout"),
    (False, "ModuleNotFoundError: nonexistent\nFAILED tests/test_bug.py::test_b\n1 failed", "setup_error"),
    (False, '1 failing\nAssertionError\n"before all" hook for test', "setup_error"),
    (False, "FAILED tests/test_b.py::test_b\n1 failed, 1 error\nERROR at setup of test_c", "setup_error"),
    (False, "SyntaxError: invalid syntax\n1 failing", "setup_error"),
    (False, "Missing script: test:new", "setup_error"),
    (False, "1 failing\nTestingLibraryElementError: Unable to find listbox", "inconclusive"),
    (False, "exit 1", "inconclusive"),
])
def test_failure_classification_never_equates_nonzero_with_reproduction(passed, output, expected):
    assert classify(Check(name="base", passed=passed, evidence=output)) == expected


def repo_fixture(tmp_path):
    def git(*args):
        return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(tmp_path), *args],
            check=True, capture_output=True).stdout
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("config", "user.name", "fixture")
    git("config", "user.email", "fixture@example.com")
    (tmp_path / "service.py").write_text("value = 1\n")
    git("add", "--all")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD").decode().strip()
    return git, base


def test_overlay_replays_exact_public_test_bytes_without_candidate_production(tmp_path):
    git, base = repo_fixture(tmp_path)
    (tmp_path / "service.py").write_text("value = 2\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/[space] bug.py").write_bytes(b"from service import value\nassert value == 2\n")
    git("add", "--all")
    git("commit", "-qm", "candidate")
    head = git("rev-parse", "HEAD").decode().strip()
    patch, paths = project_tests(SimpleNamespace(workspace=str(tmp_path), base_commit=base, candidate_commit=head))
    assert paths == ["tests/[space] bug.py"]
    git("reset", "--hard", base)
    subprocess.run(["git", "-C", str(tmp_path), "apply", "--binary", "-"],
        input=patch, check=True, capture_output=True)
    assert (tmp_path / "service.py").read_text() == "value = 1\n"
    assert (tmp_path / paths[0]).read_bytes() == b"from service import value\nassert value == 2\n"


@pytest.mark.skipif(os.name == "nt", reason="Real symlink modes verified on native Linux")
def test_overlay_rejects_changed_symlinks(tmp_path):
    git, base = repo_fixture(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_escape.py").symlink_to("/etc/passwd")
    git("add", "--all")
    git("commit", "-qm", "link")
    with pytest.raises(ValueError, match="regular files"):
        project_tests(SimpleNamespace(workspace=str(tmp_path), base_commit=base,
            candidate_commit=git("rev-parse", "HEAD").decode().strip()))


def mock_base(monkeypatch, tmp_path, result, mutate=False):
    import benchmarks.polybench.regression as module
    removed, executed, events = [], [], []
    container = SimpleNamespace(id="base-offline", remove=lambda **kw: removed.append(kw))
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/repo"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "test_projection", lambda *a: (b"", []))
    trees = iter([b"before", b"changed" if mutate else b"before"])
    def command(_container, argv, *_args):
        executed.append(argv)
        return next(trees) if argv == ["git", "write-tree"] else b""
    monkeypatch.setattr(module, "command", command)
    def check(name, argv, *args):
        executed.append(argv)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(module, "command_check", check)
    candidate = Candidate(base_commit="a", input_commit="a", candidate_commit="b",
        workspace=str(tmp_path), changed_files=["service.py"], diff_sha256="c",
        verification_commands=[["pytest", "tests/test_behavior.py"]])
    return candidate, removed, executed, lambda e, d: events.append((e, d))


@pytest.mark.parametrize("output,passed,expected", [
    ("FAILED tests/test_behavior.py::test_b\n1 failed", False, True),
    ("1 passed", True, False),
    ("ModuleNotFoundError\nFAILED tests/test_behavior.py::test_b\n1 failed", False, False),
])
def test_base_replay_requires_observed_behavior_and_records_evidence(monkeypatch, tmp_path, output, passed, expected):
    candidate, removed, executed, emit = mock_base(monkeypatch, tmp_path,
        Check(name="base_test_1", passed=passed, evidence=output))
    result = regression_check(candidate, SimpleNamespace(base_commit="a"), tmp_path, Settings(), None,
        {}, lambda: None, emit)
    assert result.passed is expected
    assert removed == [{"force": True}]
    assert ["git", "reset", "--hard", "a"] in executed
    replay = next(a for a in executed if a[0] == "docker")
    assert "1000:1000" in replay and "BABEL_DISABLE_CACHE=1" in replay
    assert not any("CODEX_HOME" in a for a in replay)
    saved = json.loads((tmp_path / "regression.json").read_text())
    assert saved["model_calls"] == 0 and saved["passed"] is expected
    assert saved["limitation"] == LIMITATION


def test_mutating_base_source_cannot_establish_reproduction(monkeypatch, tmp_path):
    candidate, removed, _, emit = mock_base(monkeypatch, tmp_path,
        Check(name="base", passed=False, evidence="AssertionError\n1 failing"), mutate=True)
    assert not regression_check(candidate, SimpleNamespace(base_commit="a"), tmp_path, Settings(), None,
        {}, lambda: None, emit).passed
    assert json.loads((tmp_path / "regression.json").read_text())["category"] == "mutated_source"
    assert removed == [{"force": True}]


def test_cancellation_propagates_and_removes_base_container(monkeypatch, tmp_path):
    candidate, removed, _, emit = mock_base(monkeypatch, tmp_path, Cancelled("stop"))
    with pytest.raises(Cancelled):
        regression_check(candidate, SimpleNamespace(base_commit="a"), tmp_path, Settings(), None,
            {}, lambda: None, emit)
    assert removed == [{"force": True}]


def test_candidate_green_without_base_red_blocks_bug_readiness(monkeypatch, tmp_path):
    import benchmarks.polybench.engine as module
    removed = []
    container = SimpleNamespace(id="candidate", remove=lambda **kw: removed.append(kw))
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/repo"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "assert_clean", lambda *a: None)
    monkeypatch.setattr(module, "command_check", lambda name, *a: Check(name=name, passed=True, evidence="1 passed"))
    monkeypatch.setattr(module, "regression_check", lambda *a: Check(
        name="public_regression_reproduced", passed=False, evidence="Original also passes"))
    candidate = Candidate(base_commit="a", input_commit="a", candidate_commit="b",
        workspace=str(tmp_path), changed_files=["service.js"], diff_sha256="c",
        verification_commands=[["yarn", "test"]])
    verifier = VisibleVerifier(Settings(), None, {})
    task = SimpleNamespace(base_commit="a", kind="bug", report="Repair reported behavior")
    result = verifier.run(candidate, task, tmp_path, lambda: None, lambda *a: None)
    assert not result.passed
    assert removed == [{"force": True}]
    assert any("not proof of issue relevance" in gap for gap in result.known_gaps)
    task.kind = "feature"
    assert verifier.run(candidate, task, tmp_path, lambda: None, lambda *a: None).passed


def test_differential_gate_does_not_claim_issue_completeness():
    # A contrived proxy assertion can be red/green too. This limitation must stay
    # visible even when reproduction succeeds; it is not an independent judge.
    check = Check(name="proxy", passed=False, evidence="AssertionError\n1 failing")
    assert classify(check) == "behavioral_failure"
    assert "unrelated or fabricated" in LIMITATION


def test_actual_replay_ingests_large_report_before_summarizing(monkeypatch, tmp_path):
    import benchmarks.polybench.regression as module
    candidate, _, _, emit = mock_base(monkeypatch, tmp_path,
        Check(name='base', passed=False, evidence='short summary with no report'))
    report = {'stats': {'tests': 1, 'passes': 0, 'failures': 1, 'pending': 0},
              'tests': [], 'padding': 'x' * 3_000_000,
              'failures': [{'fullTitle': 'reported behavior', 'err': {'stack': 'AssertionError: missing ID', 'message': 'missing ID'}}]}
    def execute_check(name, argv, cwd, env, logs, *args):
        logs.mkdir(parents=True)
        (logs / 'stdout.txt').write_text(json.dumps(report))
        (logs / 'stderr.txt').write_text('Browserslist outdated')
        return Check(name=name, passed=False, evidence='short summary')
    monkeypatch.setattr(module, 'command_check', execute_check)
    result = regression_check(candidate, SimpleNamespace(base_commit='a'), tmp_path,
        Settings(), None, {}, lambda: None, emit)
    assert result.passed
    saved = json.loads((tmp_path / 'regression.json').read_text())
    ingestion = saved['commands'][0]['ingestion']
    assert ingestion['bytes_read']['stdout.txt'] > 2_000_000
    assert ingestion['reports'][0]['stats']['failures'] == 1


def test_oversized_report_never_classifies_only_stderr(tmp_path):
    from benchmarks.polybench.regression import classify_public_logs
    (tmp_path / 'stdout.txt').write_bytes(b'x' * 20_000_001)
    (tmp_path / 'stderr.txt').write_text('1 passing')
    category, evidence = classify_public_logs(Check(name='test', passed=True, evidence='1 passing'), tmp_path, Settings())
    assert category == 'report_oversized'
    assert evidence['error']


def test_large_report_does_not_hide_setup_error_or_timeout(tmp_path):
    from benchmarks.polybench.regression import classify_public_logs
    (tmp_path / 'stdout.txt').write_text('x' * 3_000_000 + '\nAssertionError\n1 failing')
    (tmp_path / 'stderr.txt').write_text('Cannot find module broken')
    check = Check(name='test', passed=False, evidence='failed')
    assert classify_public_logs(check, tmp_path, Settings())[0] == 'setup_error'
    check.evidence = 'Child tree terminated'
    assert classify_public_logs(check, tmp_path, Settings())[0] == 'timeout'
