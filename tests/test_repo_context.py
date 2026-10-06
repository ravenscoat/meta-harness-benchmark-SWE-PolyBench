import json
import subprocess

import pytest

from benchmarks.polybench import repo_context as module


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_context_tracks_only_public_sources(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "arrays.py").write_text("import math\ndef linspace(start, stop):\n    return stop - start\n")
    (tmp_path / "test_arrays.py").write_text("def test_linspace():\n    assert True\n")
    (tmp_path / "auth.json").write_text('{"secret":"never-output"}')
    (tmp_path / ".env.local").write_text("secret=never-output")
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"node --test","build":"echo build"}}')
    git(tmp_path, "add", ".")
    (tmp_path / "untracked.py").write_text("def linspace(): pass")
    result = module.inspect(tmp_path, "linspace arrays")
    assert result["tracked_file_count"] == 3
    assert result["matches"][0]["path"] == "arrays.py"
    assert result["matches"][0]["outline"]["symbols"][0]["name"] == "linspace"
    assert result["test_files"] == ["test_arrays.py"]
    assert result["declared_test_scripts"][0]["script"] == "test:unit"
    assert "never-output" not in json.dumps(result)
    assert "untracked.py" not in json.dumps(result)


def test_bounds_and_malformed_manifests(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "huge.py").write_text("a" * (module.MAX_READ + 1))
    (tmp_path / "broken.py").write_text("def match broken")
    (tmp_path / "package.json").write_text("[]")
    git(tmp_path, "add", ".")
    result = module.inspect(tmp_path, "match huge", limit=999)
    assert result["matches"][0]["outline"]["status"] == "parse_error"
    assert len(result["matches"]) == 1
    assert result["declared_test_scripts"] == []


def test_gitlink_is_not_read(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "update-index", "--add", "--cacheinfo", "160000," + "a" * 40 + ",vendor")
    assert module.inspect(tmp_path, "vendor")["tracked_file_count"] == 0


def test_python37_ast_import_fallback(monkeypatch):
    monkeypatch.delattr(module.ast, "get_source_segment", raising=False)
    result = module.outline("import math\ndef shape(): return math.pi\n", ".py")
    assert result["imports"] == ["import math"]
    assert result["symbols"][0]["name"] == "shape"


def test_symlink_and_parent_escape_are_omitted(tmp_path):
    git(tmp_path, "init")
    outside = tmp_path.parent / "outside-public-tool-fixture"
    outside.mkdir(exist_ok=True)
    (outside / "secret.py").write_text("def secret(): pass\n")
    try:
        (tmp_path / "escape.py").symlink_to(outside / "secret.py")
    except OSError:
        pytest.skip("Symlink creation unavailable; Linux check covers this path")
    git(tmp_path, "add", "escape.py")
    # Also simulate a directory replaced by an escaping link after staging.
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "secret.py").write_text("def secret(): pass\n")
    git(tmp_path, "add", "nested/secret.py")
    (tmp_path / "nested" / "secret.py").unlink()
    (tmp_path / "nested").rmdir()
    (tmp_path / "nested").symlink_to(outside, target_is_directory=True)
    assert module.inspect(tmp_path, "secret")["tracked_file_count"] == 0
