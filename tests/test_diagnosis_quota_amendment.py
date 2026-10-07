"""User exception never fabricates usage or bypasses account exhaustion."""
import pytest

from scripts.run_diagnosis_quota_continuation import quota_allowed


@pytest.mark.parametrize('primary,weekly,ordinary,exception,allowed', [
    (85, 27, True, True, True), (85, 27, True, False, False),
    (100, 27, True, True, False), (85, 90, True, True, False),
    (85, 27, False, True, False), (79, 27, True, False, True),
])
def test_one_trial_exception_preserves_real_exhaustion_and_weekly_guard(
        primary, weekly, ordinary, exception, allowed):
    assert quota_allowed({'primary': {'usedPercent': primary},
                          'secondary': {'usedPercent': weekly},
                          'ordinary_allowed': ordinary}, exception) is allowed
