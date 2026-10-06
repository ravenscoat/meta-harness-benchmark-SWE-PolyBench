from types import SimpleNamespace

import pytest

from benchmarks.polybench.dependencies import share_public_fixture
from hx.models import HXError


def test_only_public_named_tokenizer_is_copied_offline():
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(exit_code=0, output=b"cached")
    assert share_public_fixture(SimpleNamespace(exec_run=run), "huggingface/transformers")
    code = calls[-1][0][-1]
    assert "local_files_only=True" in code and "token=False" in code
    assert "models--HuggingFaceM4--tiny-random-idefics" in code
    assert "/tmp/hx-home/.cache/huggingface/hub" in code
    assert "auth.json" not in code
    assert calls[-1][1]["environment"]["HF_HUB_OFFLINE"] == "1"


def test_non_fixture_case_does_no_transfer():
    assert not share_public_fixture(None, "example/project")


def test_missing_public_cache_is_operational_error():
    count = 0
    def run(*args, **kwargs):
        nonlocal count
        count += 1
        return SimpleNamespace(exit_code=0 if count == 1 else 1, output=b"missing cached resource")
    with pytest.raises(HXError, match="cache transfer failed"):
        share_public_fixture(SimpleNamespace(exec_run=run), "huggingface/transformers")


def test_visible_checks_disconnect_before_candidate_and_commands(monkeypatch, tmp_path):
    import benchmarks.polybench.engine as module
    from hx.models import Candidate, Check, Settings
    order = []
    networks = {"bridge": {}}
    container = SimpleNamespace(id="candidate", attrs={"NetworkSettings": {"Networks": networks}},
        reload=lambda: None, remove=lambda **kwargs: order.append("removed"))
    def disconnect(_):
        order.append("offline")
        networks.clear()
    client = SimpleNamespace(networks=SimpleNamespace(get=lambda name:
        SimpleNamespace(disconnect=disconnect)))
    def create(*args, **kwargs):
        assert kwargs["offline"] is False
        return container, "/testbed"
    monkeypatch.setattr(module, "create", create)
    monkeypatch.setattr(module, "prepare_dependencies", lambda *args: order.append("dependencies"))
    monkeypatch.setattr(module, "share_public_fixture", lambda *args: order.append("cache"))
    monkeypatch.setattr(module, "populate", lambda *args: order.append("candidate"))
    monkeypatch.setattr(module, "assert_clean", lambda *args: None)
    def check(name, argv, *args):
        assert not networks
        order.append(name)
        return Check(name=name, passed=True, evidence="observed")
    monkeypatch.setattr(module, "command_check", check)
    candidate = Candidate(base_commit="a", input_commit="a", candidate_commit="b",
        changed_files=[], workspace=str(tmp_path), diff_sha256="hash",
        verification_commands=[["pytest", "tests/test_public.py"]])
    verifier = module.VisibleVerifier(Settings(), client,
        {"repo": "huggingface/transformers", "upstream_base": "original"})
    assert verifier.run(candidate, SimpleNamespace(base_commit="a"), tmp_path,
        lambda: None, lambda *args: None).passed
    assert order[:4] == ["dependencies", "cache", "offline", "candidate"]
    assert order[-1] == "removed"
