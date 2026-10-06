from benchmarks.advanced.runner import AdvancedEngine, review_policy_context
from hx.models import Review, Settings, Task
from hx.optimization import BASE_POLICY
from hx.store import Store


def test_review_policy_uses_frozen_candidate_and_preserves_evidence(tmp_path, monkeypatch):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/app.py").write_text("CANDIDATE = 'sealed'\n")
    policy = BASE_POLICY.model_copy(
        update={
            "instructions": "Inspect actual callers, not guessed filenames.",
            "context_files": ["backend/app.py"],
            "environment_snapshot": True,
        }
    )
    original = {"candidate_commit": "exact", "verification": {"passed": True}}
    monkeypatch.setattr(
        "benchmarks.advanced.runner.git", lambda *args: "backend/app.py\nfrontend/src/main.jsx"
    )
    context = review_policy_context(policy, tmp_path, original)
    assert context["candidate_commit"] == "exact"
    assert context["verification"] == original["verification"]
    assert context["selected_source"]["backend/app.py"] == "CANDIDATE = 'sealed'\n"
    assert context["environment"]["files"] == ["backend/app.py", "frontend/src/main.jsx"]
    assert "Read-only" in context["environment"]["permission"]
    assert "harness_guidance" not in original
    assert (tmp_path / "backend/app.py").read_text() == "CANDIDATE = 'sealed'\n"


def test_standard_policy_adds_no_source_or_environment(tmp_path):
    context = review_policy_context(BASE_POLICY, tmp_path, {"candidate_commit": "exact"})
    assert context["harness_guidance"] == ""
    assert context["selected_source"] == {}
    assert "environment" not in context


def test_advanced_engine_forwards_guidance_to_reviewers_only(tmp_path, monkeypatch):
    policy = BASE_POLICY.model_copy(
        update={"instructions": "Ground inspection gaps in required evidence."}
    )
    engine = AdvancedEngine(Store(tmp_path / "state"), Settings(adapter="fake"), policy)
    task = Task(
        id="review",
        repo=str(tmp_path),
        report="Inspect the actual caller and preserve its contract.",
    )
    monkeypatch.setattr("hx.optimization.ChallengeEngine._worker", lambda self, *args: args[5])
    evidence = {"candidate_commit": "exact"}
    context = engine._worker(
        "run", "security", "security", task, tmp_path, evidence, Review, tmp_path, 0
    )
    assert context["harness_guidance"] == policy.instructions
    assert context["candidate_commit"] == "exact"
    untouched = engine._worker(
        "run", "consolidate", "consolidator", task, tmp_path, evidence, Review, tmp_path, 0
    )
    assert untouched == evidence
    assert engine.config["policy_targets"] == ["implementer", "correctness", "security"]
