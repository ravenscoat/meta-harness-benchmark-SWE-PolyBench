import pytest

from scripts.supervise_ten_task_cap import scored_boundary


def test_cap_includes_already_scored_and_stops_only_at_exact_first_ten():
    plan = {"cases": [str(n) for n in range(17)]}
    amendment = {"cases": plan["cases"][:10], "max_tasks": 10}
    assert not scored_boundary(plan, amendment, [{"case": str(n)} for n in range(3)])
    assert scored_boundary(plan, amendment, [{"case": str(n)} for n in range(10)])
    with pytest.raises(RuntimeError, match="outside"):
        scored_boundary(plan, amendment, [{"case": "10"}])
    with pytest.raises(RuntimeError, match="Duplicate"):
        scored_boundary(plan, amendment, [{"case": "0"}, {"case": "0"}])
    with pytest.raises(RuntimeError, match="first ten"):
        scored_boundary(plan, {**amendment, "cases": plan["cases"][1:11]}, [])
