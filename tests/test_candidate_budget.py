from hx.models import Check, Verification


def inject_final_usage(engine, adapter, tokens):
    original = adapter.run
    def run(*args):
        result = original(*args)
        args[8]("worker.usage", {"tokens": tokens})
        return result
    adapter.run = run


def test_completed_candidate_is_verified_after_reported_token_overshoot(project, setup_engine):
    engine, adapter = setup_engine(workflow="single", max_observed_tokens=50000,
        repair_token_reserve=5000)
    inject_final_usage(engine, adapter, 60000)
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "ready_for_approval", result["error"]
    assert result["observed_tokens"] == 60000
    assert result["handoff"]["verified"]
    assert adapter.calls == {"implementer": 1}


def test_failed_candidate_is_preserved_without_unaffordable_repair(project, setup_engine):
    engine, adapter = setup_engine(workflow="single", max_observed_tokens=50000,
        repair_token_reserve=5000)
    engine = type(engine)(engine.store,
        engine.settings.model_copy(update={"max_revisions": 1}), adapter)
    inject_final_usage(engine, adapter, 49000)
    class Failure:
        def run(self, candidate, *args):
            return Verification(candidate_commit=candidate.candidate_commit, passed=False,
                checks=[Check(name="regression", passed=False, evidence="Observed failure")],
                changed_line_coverage=None, known_gaps=[])
    engine.verifier = Failure()
    run = engine.create(project["missing-task"])
    result = engine.execute(run["id"])
    assert result["status"] == "needs_attention", result["error"]
    assert result["handoff"]["candidate_commit"]
    assert not result["handoff"]["verified"]
    assert adapter.calls == {"implementer": 1}
    assert any(e["type"] == "budget.repair_skipped" for e in engine.store.events(run["id"]))
