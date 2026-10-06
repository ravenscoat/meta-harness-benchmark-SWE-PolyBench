import json
from pathlib import Path

import pytest

from hx.code_search import (
    CodeProposal,
    copy_experience,
    dominates,
    evaluate,
    frontier,
    seal,
    search_cases,
    validate_source,
)
from hx.environment import snapshot
from hx.models import HXError


def test_schema_requires_all_properties():
    schema = CodeProposal.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("source", [
    "import os\ndef focused_output(output,limit=2000): return os.getenv('SECRET')",
    "def focused_output(output,limit=2000): return open('auth.json').read()",
    "import re\ndef focused_output(output,limit=2000): return re.__dict__",
    "def focused_output(output,limit=2000): return getattr(output,'upper')()",
    "@print\ndef focused_output(output,limit=2000): return output",
])
def test_pure_candidate_rejects_capabilities(source):
    with pytest.raises(HXError):
        validate_source(source.encode())


def test_experience_is_explicit_and_sealed(tmp_path):
    public = tmp_path / "trace.txt"
    public.write_text("Full public command trace, not a compressed summary")
    private = tmp_path / "auth.json"
    private.write_text("never import")
    archive = tmp_path / "archive"
    lock = copy_experience(archive, {"attempt/trace.txt": public})
    assert lock == seal(archive)
    assert list(lock) == ["attempt/trace.txt"]
    assert not (archive / "auth.json").exists()
    with pytest.raises(FileExistsError):
        copy_experience(archive, {"trace.txt": public})


def test_archive_rejects_escape(tmp_path):
    source = tmp_path / "public.txt"
    source.write_text("public")
    with pytest.raises(HXError):
        copy_experience(tmp_path / "archive", {"../outside.txt": source})


def test_dominance_requires_quality_and_cost(tmp_path):
    incumbent = {"quality": 3, "context_characters": 2000}
    better = {"quality": 4, "context_characters": 800}
    expensive = {"quality": 4, "context_characters": 3000}
    assert dominates(better, incumbent)
    assert not dominates(expensive, incumbent)
    assert not dominates(incumbent, incumbent)
    assert frontier({"old": incumbent, "good": better, "expensive": expensive}) == ["good"]


def test_search_actually_detects_incumbent_blind_spots(tmp_path):
    source = Path(__file__).parents[1] / "src/hx/failure_evidence.py"
    result = evaluate(source, search_cases(), tmp_path / "evaluation")
    assert result["count"] == 4
    assert 0 <= result["quality"] <= 4
    assert json.loads((tmp_path / "evaluation/score.json").read_text()) == result


def test_oversized_output_rejected_and_logs_retained(tmp_path):
    source = tmp_path / "candidate.py"
    source.write_text("def focused_output(output,limit=2000): return output\n")
    with pytest.raises(HXError, match="evaluation failed"):
        evaluate(source, search_cases(), tmp_path / "failed")
    assert (tmp_path / "failed/stderr.txt").exists()


def test_environment_snapshot_does_not_execute_repository_code(monkeypatch):
    import hx.environment as module
    monkeypatch.setattr(module.shutil, "which", lambda name: "/tools/" + name)
    value = snapshot()
    assert value["available_tools"]["node"] == "/tools/node"
    assert "controller" in value["scope"]
    assert "Availability only" in value["limits"]


@pytest.mark.parametrize("limit", [0, 1, 7, 23, 800])
def test_current_extractor_handles_tiny_budgets_without_overflow(limit):
    from hx.failure_evidence import focused_output
    raw = "ERROR setup details " * 100 + "\nAssertionError: distinct failure\n" + "warning\n" * 100
    assert len(focused_output(raw, limit)) <= limit


def test_completed_archive_detects_new_unsealed_files(tmp_path):
    from hx.config import canonical
    from scripts.code_search_history import read
    (tmp_path / "failure.json").write_text('{"adopted": false}')
    files = seal(tmp_path)
    (tmp_path / "archive-lock.json").write_bytes(canonical({"files": files}))
    assert read(tmp_path)["outcome"]["adopted"] is False
    (tmp_path / "extra.txt").write_text("unexpected")
    with pytest.raises(HXError, match="inventory changed"):
        read(tmp_path)


def test_logged_patch_recovery_rejects_an_additional_file(tmp_path):
    from scripts.recover_code_search import logged_patch
    trace = tmp_path / "stdout.txt"
    patch = "diff --git a/src/hx/failure_evidence.py b/src/hx/failure_evidence.py\n" + \
        "--- a/src/hx/failure_evidence.py\n+++ b/src/hx/failure_evidence.py\n@@ -1 +1 @@\n-old\n+new\n" + \
        "diff --git a/hx.toml b/hx.toml\n--- a/hx.toml\n+++ b/hx.toml\n@@ -1 +1 @@\n-old\n+bad\n"
    trace.write_text(json.dumps({"item": {"type": "command_execution", "status": "completed",
        "aggregated_output": patch}}) + "\n")
    with pytest.raises(HXError, match="more than"):
        logged_patch(trace)


def test_timeout_recovery_is_a_separate_model_free_identity(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import scripts.run_code_search as module
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.recover_interrupted(tmp_path / "candidate") == 0
    assert calls[0][0][2] == "scripts.recover_code_search"
    assert calls[0][0][-1].endswith("candidate-recovery")
    assert "codex" not in " ".join(calls[0][0])
