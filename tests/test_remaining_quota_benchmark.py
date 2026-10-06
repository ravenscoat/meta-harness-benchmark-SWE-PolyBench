from scripts.run_remaining_quota_benchmark import can_start_remaining


def test_explicit_remaining_quota_boundaries():
    def quota(primary=1, weekly=90, allowed=True):
        return {'ordinary_allowed': allowed, 'primary': {'usedPercent': primary},
                'secondary': {'usedPercent': weekly}}

    assert can_start_remaining(quota())
    assert can_start_remaining(quota(weekly=97))
    assert not can_start_remaining(quota(weekly=98))
    assert not can_start_remaining(quota(primary=80))
    assert not can_start_remaining(quota(allowed=False))
