import json

import pytest

from hx.meta import Proposal, candidate_settings, public_evidence, settings_toml
from hx.models import HXError, Settings


def proposal(**changes):
    value = dict(name="compact", rationale="Keep useful failure evidence while reserving repair budget.",
        priorities=["budget", "context"], evidence_ids=["public-case"],
        repository_matches=4, repair_feedback_chars=1200, repair_token_reserve=30000,
        limitations=["Fixture success is not model performance."])
    return Proposal(**{**value, **changes})


def test_proposal_schema_requires_every_field():
    schema = Proposal.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])


def test_meta_only_changes_bounded_runtime_knobs():
    settings = Settings(workflow="single")
    candidate = candidate_settings(settings, proposal())
    changed = {k for k, v in settings.model_dump().items() if candidate.model_dump()[k] != v}
    assert changed == {"repository_matches", "repair_feedback_chars", "repair_token_reserve"}
    assert candidate.max_observed_tokens == settings.max_observed_tokens
    assert candidate.worker_model == "gpt-6-luna"


def test_meta_cannot_consume_entire_model_budget():
    with pytest.raises(HXError):
        candidate_settings(Settings(max_observed_tokens=10000), proposal())


def test_contradictory_model_proposal_is_rejected():
    with pytest.raises(HXError, match="contradicts"):
        candidate_settings(Settings(), proposal(rationale="Increase failed-check feedback from 2000 to 8000 characters.",
            repair_feedback_chars=800))


def test_failure_excerpt_keeps_error_before_long_warning_tail():
    from hx.failure_evidence import focused_output
    raw = "Traceback\nOSError: Cannot find tokenizer locally\n" + ("warning: deprecated\n" * 1000)
    excerpt = focused_output(raw, 800)
    assert "Cannot find tokenizer" in excerpt
    assert len(excerpt) <= 800


def test_public_run_export_excludes_acceptance_diagnostics():
    from types import SimpleNamespace

    from hx.meta import export_public_runs
    ver = {"candidate_commit": "commit", "passed": False, "changed_line_coverage": None,
        "known_gaps": [], "checks": [{"name": "public_test", "passed": False,
            "evidence": "Observed public assertion"}, {"name": "acceptance", "passed": False,
            "evidence": "PRIVATE_SENTINEL"}]}
    store = SimpleNamespace(list=lambda: [{"id": "run", "status": "needs_attention"}],
        steps=lambda _: [{"id": "verify_0", "status": "completed", "cache_key": "key"}],
        cached=lambda *args: ver, events=lambda _: [])
    rows = export_public_runs(store)
    assert "PRIVATE_SENTINEL" not in json.dumps(rows)
    assert "Observed public assertion" in json.dumps(rows)


def test_config_serialization_roundtrip():
    import tomllib
    settings = candidate_settings(Settings(), proposal())
    assert Settings.model_validate(tomllib.loads(settings_toml(settings).decode())) == settings


def test_public_projection_omits_private_and_unbounded_fields(tmp_path):
    path = tmp_path / "public.json"
    path.write_text(json.dumps([{"case": "public-case", "test_patch": "PRIVATE_SENTINEL",
        "private_evaluation": "PRIVATE_SENTINEL", "reviews": [],
        "public_verification": [{"checks": [{"name": "test", "passed": False,
            "tail": "x" * 10000}]}]}]))
    evidence = public_evidence(path)
    assert "PRIVATE_SENTINEL" not in json.dumps(evidence)
    assert len(evidence["cases"][0]["public_checks"][0]["tail"]) == 1500
