import pytest

from hx.models import Check, GateError, Verification


def test_single_worker_real_verification_and_approval(project, setup_engine):
    engine, adapter = setup_engine(workflow="single")
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    assert adapter.calls == {"implementer": 1}
    assert result["handoff"]["verified"]
    assert not result["handoff"]["reviewed"]
    assert result["handoff"]["review_steps"] == []
    events = engine.store.events(run["id"])
    assert any(e["type"] == "tool.repository_map" for e in events)
    assert any(e["type"] == "tool.environment_snapshot" for e in events)
    assert any(e["type"] == "tool.patch_replay" and e["data"]["passed"] for e in events)
    engine.decision(run["id"], result["handoff"]["candidate_commit"], True)


def test_single_failed_checks_cannot_be_approved(project, setup_engine):
    engine, adapter = setup_engine(workflow="single")
    class FailedVerifier:
        def run(self, candidate, *args):
            return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                checks=[Check(name="behavior", passed=False, evidence="actual failure")],
                changed_line_coverage=None, known_gaps=[])
    engine.verifier = FailedVerifier()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention", result["error"]
    assert adapter.calls == {"implementer": 1}
    with pytest.raises(GateError):
        engine.decision(run["id"], result["handoff"]["candidate_commit"], True)


def test_single_repairs_from_bounded_feedback_without_review_calls(project, setup_engine):
    engine, adapter = setup_engine(workflow="single")
    engine = type(engine)(engine.store,
        engine.settings.model_copy(update={"max_revisions": 1}), adapter)
    contexts = []
    original = adapter.run
    def record(role, task, workspace, context, *args):
        contexts.append(context)
        return original(role, task, workspace, context, *args)
    adapter.run = record
    class RetryVerifier:
        calls = 0
        def run(self, candidate, *args):
            self.calls += 1
            passed = self.calls == 2
            return Verification(candidate_commit=candidate.candidate_commit, passed=passed,
                checks=[Check(name="behavior", passed=passed, evidence="x" * 10000)],
                changed_line_coverage=None, known_gaps=[])
    engine.verifier = RetryVerifier()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    assert result["handoff"]["revisions_used"] == 1
    assert adapter.calls == {"implementer": 2}
    # Contract is a nonempty upper bound; concise evidence need not pad to the cap.
    assert 0 < len(contexts[1]["repair_plan"]["failed_checks"][0]["evidence"]) <= 2000
    assert "reviews" not in contexts[1]


@pytest.mark.parametrize("argv", [
    ["yarn", "mocha", "test/a.js"], ["pnpm", "vitest", "run"],
    ["./node_modules/.bin/mocha", "test/a.js"], ["jest", "--runInBand"],
])
def test_installed_test_entrypoints(argv):
    from benchmarks.polybench.public_checks import public_test_argv
    assert public_test_argv(argv)


@pytest.mark.parametrize("argv", [["npx", "mocha"], ["npm", "exec", "jest"],
    ["sh", "-c", "mocha"], ["./untrusted/mocha"], ["yarn", "install"]])
def test_installers_and_shells_still_rejected(argv):
    from benchmarks.polybench.public_checks import public_test_argv
    assert not public_test_argv(argv)
