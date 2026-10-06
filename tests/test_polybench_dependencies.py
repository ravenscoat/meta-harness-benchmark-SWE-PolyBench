from types import SimpleNamespace

import pytest

from benchmarks.polybench.dependencies import prepare_dependencies
from hx.models import HXError


def test_bootstrap_requires_original_base_before_network(tmp_path):
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(exit_code=0, output=b"different-base\n")

    with pytest.raises(HXError, match="unchanged upstream base"):
        prepare_dependencies(SimpleNamespace(exec_run=execute), "microsoft/vscode", tmp_path, "base")
    assert len(calls) == 1


def test_bootstrap_records_download_and_checks_executable(tmp_path):
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(exit_code=0, output=b"base\n" if argv[0] == "git" else b"dependency evidence")

    prepare_dependencies(SimpleNamespace(exec_run=execute), "microsoft/vscode", tmp_path, "base")
    assert calls[1] == ["timeout", "300", "yarn", "electron"]
    assert calls[2][0] == "node"
    assert (tmp_path / "electron-bootstrap.txt").read_bytes() == b"dependency evidence"
    assert (tmp_path / "electron-probe.txt").exists()


def test_non_vscode_repositories_do_not_bootstrap(tmp_path):
    prepare_dependencies(None, "example/project", tmp_path / "missing", "base")
    assert not (tmp_path / "missing").exists()


def test_public_transformers_fixture_is_cached_without_running_tests(tmp_path):
    calls = []
    environments = []

    def execute(argv, **kwargs):
        calls.append(argv)
        environments.append(kwargs.get("environment"))
        return SimpleNamespace(exit_code=0, output=b"base\n" if argv[0] == "git" else b"public snapshot revision")

    prepare_dependencies(SimpleNamespace(exec_run=execute), "huggingface/transformers", tmp_path, "base")
    assert calls[0][0] == "grep"
    assert calls[-1][:4] == ["timeout", "300", "python", "-c"]
    assert "token=False" in calls[-1][-1]
    assert environments[-1] == {"HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"}
    assert environments[:-1] == [None, None]
    assert (tmp_path / "public-fixture-bootstrap.txt").exists()


def test_transformers_without_public_fixture_does_not_download(tmp_path):
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(exit_code=1, output=b"")

    prepare_dependencies(SimpleNamespace(exec_run=execute), "huggingface/transformers", tmp_path, "base")
    assert len(calls) == 1
    assert not (tmp_path / "public-fixture-bootstrap.txt").exists()
