import pytest

from scripts.run_hx_improvement import operational_failure


@pytest.mark.parametrize("error", [None, "revise_1 exhausted its attempt budget: worker made no changes",
                                  "observed token budget exhausted (usage reported at turn boundaries)"])
def test_coding_failure_does_not_abort_other_probes(error):
    assert not operational_failure({"error": error, "grader_error": None})


@pytest.mark.parametrize("error,grader", [
    ("Codex turn failed: invalid_json_schema", None),
    ("container command failed: executable missing", None),
    ("rate limit reached", None), (None, "test container failed"),
])
def test_operational_failure_still_stops_batch(error, grader):
    assert operational_failure({"error": error, "grader_error": grader})
