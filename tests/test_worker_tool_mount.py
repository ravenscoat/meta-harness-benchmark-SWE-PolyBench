from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.polybench.containers import create


@pytest.mark.parametrize("worker", [False, True])
def test_only_worker_gets_single_readonly_tool_file(worker, tmp_path):
    captured = {}
    container = SimpleNamespace(start=lambda: None)

    def make(*args, **kwargs):
        captured.update(kwargs)
        return container

    client = SimpleNamespace(
        images=SimpleNamespace(get=lambda _: SimpleNamespace(id="pinned", attrs={
            "Config": {"WorkingDir": "/testbed"}})),
        containers=SimpleNamespace(create=make),
    )
    binary = tmp_path / "bin" / "codex" if worker else None
    create(client, {"image_id": "pinned"}, binary=binary, offline=True)
    tool_binds = [(host, bind) for host, bind in captured["volumes"].items()
                  if bind["bind"].startswith("/opt/hx-tools")]
    if worker:
        assert len(tool_binds) == 1
        host, bind = tool_binds[0]
        assert Path(host).is_file()
        assert Path(host).name == "repo_context.py"
        assert bind == {"bind": "/opt/hx-tools/repo_context.py", "mode": "ro"}
        assert not any(Path(host).name in {"polybench", "grader.py"}
                       for host in captured["volumes"])
    else:
        assert not tool_binds
    assert captured["network_mode"] == "none"
