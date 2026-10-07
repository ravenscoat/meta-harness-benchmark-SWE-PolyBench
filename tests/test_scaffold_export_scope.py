import subprocess

import pytest

from benchmarks.polybench import containers
from hx.models import GateError


def test_only_candidate_exports_even_with_untracked_dependency_symlinks(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path)

    git("init")
    (tmp_path / "candidate_scaffold.py").write_text("def next_action(state): return {}\n")
    (tmp_path / "reference.txt").write_text("protected interface")
    git("add", ".")
    git("-c", "user.name=HX", "-c", "user.email=hx@local", "commit", "-qm", "inputs")
    (tmp_path / "candidate_scaffold.py").write_text("def next_action(state): return {'action': 'finish'}\n")
    cache = tmp_path / "node_modules"
    cache.mkdir()
    (cache / "large.bin").write_bytes(b"cache" * 10000)
    try:
        (cache / "link").symlink_to(cache / "large.bin")
    except OSError:
        pass  # Windows may lack symlink privilege; actual Linux run exercises it.

    monkeypatch.setattr(containers, "command", lambda container, argv, workdir: git(*argv[1:]))
    paths = containers.scaffold_export_paths(None, str(tmp_path), "hx/worker-scaffold")
    git("add", "--all", *paths)
    patch = git("diff", "--binary", "HEAD", *paths)
    assert b"candidate_scaffold.py" in patch
    assert b"node_modules" not in patch
    assert len(patch) < 1000
    (tmp_path / "reference.txt").write_text("changed protected input")
    with pytest.raises(GateError, match="protected"):
        containers.scaffold_export_paths(None, str(tmp_path), "hx/worker-scaffold")


def test_normal_coding_export_is_unchanged():
    assert containers.scaffold_export_paths(None, "/workspace", "mui/material-ui") == []
