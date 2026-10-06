import subprocess
from types import SimpleNamespace

import pytest

from benchmarks.polybench.delivery import is_test_path, production_patch


@pytest.mark.parametrize("path", ["tests/unit_tests/test_loader.py", "pkg/use.test.js",
    "src/component.spec.tsx", "pkg/test_build.py", "pkg/build_test.py", "__tests__/fixture.txt"])
def test_public_test_path_conventions(path):
    assert is_test_path(path)


@pytest.mark.parametrize("path", ["src/testing.py", "pkg/test_helpers.js", "pkg/latest.tsx",
    "testimonials/view.js", "src/test_service.py.txt"])
def test_production_paths_are_retained(path):
    assert not is_test_path(path)


def test_delivery_preserves_source_bytes_and_avoids_independent_test_collision(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout
    git("init", "-q")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.com")
    # Literal pathspec handling, trailing whitespace and missing final newline.
    source = repo / "[source] space.py"
    source.write_bytes(b"value = 1\n")
    git("add", "--all")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD").decode().strip()
    source.write_bytes(b"value = 2  ")
    (repo / "tests").mkdir()
    test = repo / "tests/test_new.py"
    test.write_bytes(b"assert True\n")
    git("add", "--all")
    git("commit", "-qm", "candidate")
    head = git("rev-parse", "HEAD").decode().strip()
    patch, evidence = production_patch(SimpleNamespace(workspace=str(repo), base_commit=base,
        candidate_commit=head))
    full = git("diff", "--binary", base, head)
    git("reset", "--hard", base)
    (repo / "tests").mkdir(exist_ok=True)
    test.write_bytes(b"assert 2 == 2\n")
    rejected = subprocess.run(["git", "-C", str(repo), "apply", "--check", "-"], input=full,
                              capture_output=True)
    assert rejected.returncode != 0
    subprocess.run(["git", "-C", str(repo), "apply", "--whitespace=nowarn", "-"],
                   input=patch.encode(), check=True, capture_output=True)
    assert source.read_bytes() == b"value = 2  "
    assert test.read_bytes() == b"assert 2 == 2\n"
    assert evidence["excluded_public_test_paths"] == ["tests/test_new.py"]
    assert evidence["included_paths"] == ["[source] space.py"]


def test_test_only_candidate_delivers_empty_patch(tmp_path):
    # An empty production projection cannot masquerade as a code change.
    repo = tmp_path
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout
    git("init", "-q")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.com")
    (repo / "source.py").write_text("pass\n")
    git("add", "--all")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD").decode().strip()
    (repo / "source_test.py").write_text("pass\n")
    git("add", "--all")
    git("commit", "-qm", "test")
    head = git("rev-parse", "HEAD").decode().strip()
    patch, evidence = production_patch(SimpleNamespace(workspace=str(repo), base_commit=base,
                                                       candidate_commit=head))
    assert patch == ""
    assert evidence["included_paths"] == []


def test_production_delivery_keeps_original_tests_when_candidate_updates_expectations(tmp_path):
    def git(*args):
        return subprocess.run(['git','-C',str(tmp_path),*args],check=True,capture_output=True).stdout
    git('init','-q')
    git('config','core.autocrlf','false')
    git('config','user.name','test')
    git('config','user.email','test@example.com')
    (tmp_path/'src.js').write_bytes(b'throw new Error("missing");\n')
    (tmp_path/'test').mkdir()
    (tmp_path/'test/index.js').write_bytes(b'expectError();\n')
    git('add','--all')
    git('commit','-qm','base')
    base=git('rev-parse','HEAD').decode().strip()
    (tmp_path/'src.js').write_bytes(b'console.warn("missing");\n')
    (tmp_path/'test/index.js').write_bytes(b'expectWarning();\n')
    (tmp_path/'test/new.test.js').write_bytes(b'checkUpdates();\n')
    git('add','--all')
    git('commit','-qm','candidate')
    head=git('rev-parse','HEAD').decode().strip()
    patch,evidence=production_patch(SimpleNamespace(workspace=str(tmp_path),base_commit=base,candidate_commit=head))
    assert evidence['delivered_patch_sha256']!=evidence['full_candidate_patch_sha256']
    assert set(evidence['excluded_public_test_paths'])=={'test/index.js','test/new.test.js'}
    git('reset','--hard',base)
    subprocess.run(['git','-C',str(tmp_path),'apply','--binary','-'],input=patch.encode(),check=True,capture_output=True)
    git('add','--all')
    assert (tmp_path/'src.js').read_bytes()==b'console.warn("missing");\n'
    assert (tmp_path/'test/index.js').read_bytes()==b'expectError();\n'
    assert not (tmp_path/'test/new.test.js').exists()
