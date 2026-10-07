"""Live wiring/export tests with mocked runners; no Docker/model/grader calls."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from hx.agent_search import SearchPlan
from hx.code_search import sha
from hx.models import HXError
from scripts.agent_search_polybench import PolyBenchBackend


def backend(tmp_path):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    for name in ("dataset.csv", "selection.json", "images.json", "settings.toml", "storage.json"):
        (prepared / name).write_text("{}")
    for name in ("public", "preflight"):
        (prepared / name).mkdir()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"prepared_root": str(prepared),
                                  "private_root": str(tmp_path / "private")}))
    return PolyBenchBackend(config)


def test_live_backend_exports_public_steps_without_private_grader(monkeypatch, tmp_path):
    from scripts import agent_search_polybench as module

    live = backend(tmp_path)
    monkeypatch.setenv("PATH", "original-test-path")
    (live.prepared / "images.json").write_text(json.dumps({"case": {"id": "case"}, "reserved": {"id": "reserved"}}))
    (live.prepared / "selection.json").write_text(json.dumps({"cases": [{"id": "case"}, {"id": "reserved"}]}))
    source = tmp_path / "candidate.py"
    source.write_text("def next_action(state): return {}")
    destination = tmp_path / "search/development/candidate/case"
    destination.mkdir(parents=True)

    def run_case(root, case, arm, start_guard, engine_factory):
        assert os.environ["PATH"].split(os.pathsep)[0] == str(module.runner.BINARY.parent)
        assert set(json.loads((root / "images.json").read_text())) == {case}
        assert json.loads((root / "selection.json").read_text())["cases"] == [{"id": case}]
        assert issubclass(engine_factory, module.LeanEngine)
        start_guard()
        assert (root / "search-scaffold.py").read_bytes() == source.read_bytes()
        public = root / "experiments/search-history/trial/state/runs/r1/steps/implement/attempt-1"
        public.mkdir(parents=True)
        (public / "stdout.txt").write_text("PUBLIC worker trace")
        private = root / "experiments/private-evaluation/steps"
        private.mkdir(parents=True)
        (private / "stdout.txt").write_text("PRIVATE grader trace")
        return dict(identity=str(root), official_resolved=False, visible_verified=True,
                    usage_known=True, observed_tokens=23, seconds=2, grader_error=None,
                    candidate_patch_error=None, unobserved_acceptance_tests=0,
                    acceptance={"candidate_commit": "commit"},
                    error='workflow diagnostic', status='failed')

    monkeypatch.setattr(module.runner, "run_case", run_case)
    plan = SimpleNamespace(model="fixed", reasoning_effort="medium")
    a = live.evaluate(source, "case", 1, destination, plan, lambda: None)
    bdir = tmp_path / "search/development/candidate/case-repeat2"
    bdir.mkdir()
    b = live.evaluate(source, "case", 2, bdir, plan, lambda: None)
    assert a.identity != b.identity
    assert a.public_verified and not a.official_resolved
    assert a.workflow_error == 'workflow diagnostic' and a.workflow_status == 'failed'
    exported = [p.read_text() for p in destination.rglob("*.txt")]
    assert exported == ["PUBLIC worker trace"]
    with pytest.raises(HXError, match="private search root"):
        PolyBenchBackend(live.config_path)


def test_live_backend_requires_explicit_uncontaminated_provenance(tmp_path):
    live = backend(tmp_path)
    plan = SearchPlan(development=["d1", "d2"], heldout=["h1", "h2"], proposals=1,
                      repeats=2, max_reported_tokens=100, deadline=9999999999,
                      trial_token_headroom=10, proposal_token_headroom=10,
                      model="fixed", reasoning_effort="medium",
                      source_locks={str(Path(__file__).resolve()): sha(Path(__file__).read_bytes())})
    with pytest.raises(HXError, match="provenance"):
        live.admit(plan)


def test_proposer_has_write_scope_and_only_exported_development_inputs(monkeypatch, tmp_path):
    from benchmarks.polybench import containers
    from scripts import agent_search_polybench as module

    live = backend(tmp_path)
    live.config.update(carrier_case="carrier", proposal_seconds=180)
    archive = tmp_path / "public-development"
    archive.mkdir()
    base = Path(__file__).parents[1] / "src/hx/scaffolds/single_call.py"
    (archive / "baseline.py").write_bytes(base.read_bytes())
    output = tmp_path / "proposal"
    output.mkdir()
    client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(live, "admit", lambda plan: None)
    monkeypatch.setattr(module.runner, "resources", lambda root: ({}, {"carrier": {}}, client, object()))
    monkeypatch.setattr(module, "git", lambda *args: "")

    class Adapter:
        def __init__(self, *args):
            pass

        def run(self, role, task, workspace, context, instructions, contract, directory,
                control, emit, timeout):
            assert role == "implementer"  # consolidator uses read-only sandbox
            assert task.allowed_paths == ["candidate_scaffold.py"]
            assert not (workspace / "dataset.csv").exists()
            assert not (workspace / "heldout").exists()
            source = workspace / "candidate_scaffold.py"
            source.write_text(source.read_text() + "\n# improved context\n")
            emit("worker.usage", {"tokens": 11})
            return {"diagnosis": "Reduce repeated inventories before delegation."}

    monkeypatch.setattr(containers, "ContainerAdapter", Adapter)
    proposal = live.propose(archive, output, object(), lambda: None)
    assert proposal.reported_tokens == 11
    assert proposal.usage_known
    assert "improved context" in proposal.source
