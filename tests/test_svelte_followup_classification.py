import hashlib
import json

import pytest

from benchmarks.polybench.regression import SVELTE_RUNNER_SHA256, classify, svelte_followup_policy
from hx.models import Check


def assertion(title="runtime example (shared helpers)"):
    return {"fullTitle": title, "err": {"code": "ERR_ASSERTION", "message": "2 == 4"}}


def followup(title="runtime example (inline helpers)"):
    return {"fullTitle": title, "err": {"message": "skipping test, already failed",
        "stack": "Error: skipping test, already failed\n    at Context.<anonymous> (test/runtime/index.js:64:11)"}}


def check(rows):
    return Check(name="base", passed=False, evidence=json.dumps({
        "stats": {"failures": len(rows)}, "failures": rows}))


def test_attested_svelte_followups_are_not_mistaken_for_a_second_root_failure():
    report = check([assertion(), followup("runtime example (shared helpers)"), followup()])
    assert classify(report) == "inconclusive"
    assert classify(report, {"sha256": SVELTE_RUNNER_SHA256}) == "behavioral_failure"


@pytest.mark.parametrize("rows", [
    [followup()], [followup(), assertion()],
    [assertion(), followup("runtime another-example (inline helpers)")],
    [assertion(), {"fullTitle": "runtime example (inline helpers)", "err": {"message": "unrelated error"}}],
    [assertion(), {"fullTitle": "runtime example (inline helpers)", "err": {
        "message": "skipping test, already failed", "stack": "Error at another.js:64:11"}}],
    [assertion(), followup('"before all" hook')],
])
def test_orphan_unknown_and_hook_failures_still_block_reproduction(rows):
    assert classify(check(rows), {"sha256": SVELTE_RUNNER_SHA256}) != "behavioral_failure"


def test_wrong_policy_or_report_count_cannot_authorize_followups():
    report = check([assertion(), followup()])
    assert classify(report, {"sha256": "unknown-runner"}) == "inconclusive"
    data = json.loads(report.evidence)
    data["stats"]["failures"] = 1
    assert classify(report.model_copy(update={"evidence": json.dumps(data)}),
                    {"sha256": SVELTE_RUNNER_SHA256}) == "inconclusive"


@pytest.mark.parametrize("changed,known_repo,known_source", [(False, True, True),
    (True, True, True), (False, False, True), (False, True, False)])
def test_policy_requires_known_original_and_unchanged_active_runner(
    monkeypatch, changed, known_repo, known_source
):
    import benchmarks.polybench.regression as module
    source = b"public runner"
    monkeypatch.setattr(module, "SVELTE_RUNNER_SHA256", hashlib.sha256(source).hexdigest())
    def command(container, argv, workdir):
        if argv[:2] == ["git", "ls-tree"]:
            assert argv == ['git', 'ls-tree', '-z', 'base', '--', 'test/runtime/index.js']
            return b'100644 blob ' + b'a' * 40 + b'\ttest/runtime/index.js\0'
        if argv[0] == "git":
            assert argv == ["git", "show", "base:test/runtime/index.js"]
            return source if known_source else b"unknown version"
        return b"modified runner" if changed else source
    monkeypatch.setattr(module, "command", command)
    result = svelte_followup_policy(None, "/testbed",
        {"repo": "sveltejs/svelte" if known_repo else "another/repo"}, "base")
    assert bool(result) is (not changed and known_repo and known_source)


@pytest.mark.parametrize('entry', [b'', b'120000 blob ' + b'a' * 40 +
    b'\ttest/runtime/index.js\0', b'040000 tree ' + b'a' * 40 +
    b'\ttest/runtime/index.js\0'])
def test_missing_or_nonregular_legacy_runner_skips_optional_policy(monkeypatch, entry):
    import benchmarks.polybench.regression as module
    calls = []
    def command(container, argv, workdir):
        calls.append(argv)
        assert argv[1] == 'ls-tree', 'Missing runner must not reach git show/cat'
        return entry
    monkeypatch.setattr(module, 'command', command)
    assert svelte_followup_policy(None, '/testbed', {'repo': 'sveltejs/svelte'}, 'base') is None
    assert len(calls) == 1


def test_tree_inventory_infrastructure_error_is_not_silently_skipped(monkeypatch):
    import benchmarks.polybench.regression as module
    def command(*args):
        raise RuntimeError('Git object unavailable')
    monkeypatch.setattr(module, 'command', command)
    with pytest.raises(RuntimeError, match='Git object unavailable'):
        svelte_followup_policy(None, '/testbed', {'repo': 'sveltejs/svelte'}, 'base')
