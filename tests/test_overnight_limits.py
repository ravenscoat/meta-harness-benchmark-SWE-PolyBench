import pytest

from scripts.overnight_limits import can_start, compact_usage


def response(primary=30, weekly=5, allowed=True):
    return {"ordinaryUsageAllowed": allowed, "rateLimits": {
        "primary": {"usedPercent": primary, "resetsAt": 100},
        "secondary": {"usedPercent": weekly, "resetsAt": 200},
    }}


@pytest.mark.parametrize("primary,weekly,allowed,expected", [
    (30, 5, True, True), (80, 5, True, False), (30, 90, True, False), (30, 5, False, False),
])
def test_quota_boundaries_do_not_spend_reset_credits(primary, weekly, allowed, expected):
    value = compact_usage(response(primary, weekly, allowed))
    assert can_start(value) is expected
    assert "credits" not in value


def test_missing_usage_fails_closed():
    with pytest.raises(RuntimeError, match="unavailable"):
        compact_usage({})
