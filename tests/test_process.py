import sys
import time

import pytest

from hx.models import Cancelled, HXError, StartupError
from hx.process import clean_env, execute


def test_timeout_terminates_process_and_preserves_output(tmp_path):
    before = time.monotonic()
    with pytest.raises(HXError, match="timed out"):
        execute(
            [
                sys.executable,
                "-u",
                "-c",
                "import time; print('started', flush=True); time.sleep(60)",
            ],
            tmp_path,
            clean_env(),
            tmp_path / "logs",
            0.5,
            lambda: None,
        )
    assert time.monotonic() - before < 10
    assert "started" in (tmp_path / "logs/stdout.txt").read_text("utf-8")


def test_cancellation_terminates_process(tmp_path):
    def cancel():
        raise Cancelled("cancelled")

    with pytest.raises(Cancelled):
        execute(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            tmp_path,
            clean_env(),
            tmp_path / "logs",
            60,
            cancel,
        )


def test_startup_error_is_distinct(tmp_path):
    with pytest.raises(StartupError):
        execute(
            [str(tmp_path / "missing-executable")],
            tmp_path,
            clean_env(),
            tmp_path / "logs",
            1,
            lambda: None,
        )


def test_log_budget_is_bounded(tmp_path):
    with pytest.raises(HXError, match="log budget"):
        execute(
            [sys.executable, "-c", "print('x' * 100000)"],
            tmp_path,
            clean_env(),
            tmp_path / "logs",
            5,
            lambda: None,
            max_bytes=1024,
        )


def test_secrets_not_inherited(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "another-test-secret")
    env = clean_env()
    assert "OPENAI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_descendants_do_not_outlive_normal_root_exit(tmp_path):
    before = time.monotonic()
    code, stdout, _ = execute(
        [
            sys.executable,
            "-u",
            "-c",
            "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid)",
        ],
        tmp_path,
        clean_env(),
        tmp_path / "logs",
        5,
        lambda: None,
    )
    assert code == 0
    assert stdout.strip().isdigit()
    assert time.monotonic() - before < 3
