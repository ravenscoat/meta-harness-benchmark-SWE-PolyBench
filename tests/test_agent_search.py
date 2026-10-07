"""Scripted external receipts test control logic, never real coding accuracy."""
import json
import time
from pathlib import Path

import pytest

from hx.agent_search import Proposal, SearchPlan, Trial, run_search
from hx.code_search import sha
from hx.models import HXError

BASE = Path(__file__).parents[1] / "src/hx/scaffolds/single_call.py"


def plan(**updates):
    values = dict(development=["d1", "d2"], heldout=["h1", "h2"], proposals=2,
                  repeats=2, max_reported_tokens=1000, deadline=time.time() + 60,
                  trial_token_headroom=20, proposal_token_headroom=20,
                  model="fixed-model", reasoning_effort="medium",
                  source_locks={str(BASE.resolve()): sha(BASE.read_bytes())})
    return SearchPlan(**(values | updates))


class Scripted:
    def __init__(self, defect=None):
        self.calls = []
        self.proposals = 0
        self.defect = defect

    def admit(self, plan):
        pass

    def propose(self, public, directory, plan, control):
        control()
        assert not any("h1" in p.read_text() or "h2" in p.read_text()
                       for p in public.rglob("*.json"))
        assert (public / "baseline.py").exists()
        diagnosis = public / f"diagnosis-{self.proposals + 1}.json"
        assert diagnosis.exists()
        assert json.loads(diagnosis.read_text())['trials']
        self.proposals += 1
        source = BASE.read_text() + f"\n# reusable candidate {self.proposals}\n"
        if self.defect == "invalid":
            source = "import os\ndef next_action(state): return {}"
        return Proposal(source=source, hypothesis="Avoid redundant context before delegation.",
                        reported_tokens=5, usage_known=True)

    def evaluate(self, source, case, repeat, directory, plan, control):
        control()
        baseline = source.name == "baseline.py"
        heldout = case.startswith("h")
        self.calls.append((baseline, case, repeat))
        values = dict(identity=str(directory), case=case, repeat=repeat,
                      source_sha256=sha(source.read_bytes()), model=plan.model,
                      reasoning_effort=plan.reasoning_effort, official_resolved=True,
                      public_verified=True, usage_known=True,
                      reported_tokens=10 if baseline else 6, seconds=2 if baseline else 1,
                      infrastructure_error=None, patch_error=None, missing_observations=0,
                      accepted_candidate=True, reference_informed=False)
        if self.defect == "infra":
            values["infrastructure_error"] = "setup failed"
        if self.defect == "workflow":
            values["workflow_error"] = "Session source differs from last accepted worker delivery"
            values["workflow_status"] = "failed"
        if self.defect == "unknown":
            values["usage_known"] = False
        if self.defect == "model":
            values["model"] = "different-model"
        if self.defect == "reference":
            values["reference_informed"] = True
        if self.defect == "heldout" and heldout and not baseline:
            values["official_resolved"] = False
        if self.defect == "public" and not baseline:
            values["official_resolved"] = False
        return Trial(**values)


def test_fixed_paired_search_freezes_then_validates(tmp_path):
    backend = Scripted()
    report = run_search(tmp_path / "search", plan(), BASE, backend)
    assert report["eligible_for_promotion"]
    assert report["reported_tokens"] == 162  # all three dev arms, proposer, two heldout arms
    assert backend.proposals == 2
    assert len(backend.calls) == 20
    assert [c[1] for c in backend.calls[:4]] == ["d1", "d1", "d2", "d2"]
    assert (tmp_path / "search/promoted-scaffold.py").exists()
    with pytest.raises(HXError, match="consumed"):
        run_search(tmp_path / "search", plan(), BASE, backend)


@pytest.mark.parametrize("defect", ["infra", "workflow", "unknown", "model", "reference"])
def test_operational_or_contaminated_receipts_stop_without_retry(tmp_path, defect):
    backend = Scripted(defect)
    with pytest.raises(HXError):
        run_search(tmp_path / "search", plan(), BASE, backend)
    assert len(backend.calls) == 1
    assert backend.proposals == 0
    assert (tmp_path / "search/failure.json").exists()
    assert (tmp_path / "search/archive-lock.json").exists()


@pytest.mark.parametrize("defect", ["heldout", "public", "invalid"])
def test_no_promotion_from_public_green_invalid_code_or_heldout_regression(tmp_path, defect):
    report = run_search(tmp_path / "search", plan(), BASE, Scripted(defect))
    assert not report["eligible_for_promotion"]
    assert not (tmp_path / "search/promoted-scaffold.py").exists()


def test_budget_stops_before_next_trial_and_retains_overshoot(tmp_path):
    backend = Scripted()
    with pytest.raises(HXError, match="budget"):
        run_search(tmp_path / "search", plan(max_reported_tokens=25), BASE, backend)
    assert len(backend.calls) == 1


def test_disjoint_cases_and_multiple_repeats_required():
    with pytest.raises(ValueError):
        plan(heldout=["d1", "h1"])
    with pytest.raises(ValueError):
        plan(repeats=1)


def test_proposer_cannot_change_prior_experience(tmp_path):
    class Mutator(Scripted):
        def propose(self, public, directory, plan, control):
            (public / "baseline.py").write_text("changed")
            return super().propose(public, directory, plan, control)

    with pytest.raises(HXError, match="experience"):
        run_search(tmp_path / "search", plan(), BASE, Mutator())
