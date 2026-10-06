
from types import SimpleNamespace

from hx.challenge_eval import npm_command


def test_linux_npm_resolves_native_js_not_windows_cmd(monkeypatch, tmp_path):
    import hx.challenge_eval as module
    node = tmp_path / "bin/node"
    cli = tmp_path / "share/npm/bin/npm-cli.js"
    node.parent.mkdir()
    cli.parent.mkdir(parents=True)
    node.touch()
    cli.touch()
    # Use a resolved file path here; Linux integration checks also exercise the symlink.
    monkeypatch.setattr(module, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(module.shutil, "which", lambda name:
        {"node": str(node), "npm": str(cli), "npm.cmd": "WINDOWS_SENTINEL"}.get(name))
    result = npm_command("test")
    assert result == [str(node), str(cli), "test"]
