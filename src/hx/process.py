from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from hx.models import HXError, ProcessTimeout, StartupError


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    keys = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "LANG",
        "LC_ALL",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in keys}
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    env.update(extra or {})
    return env


def kill_tree(proc: subprocess.Popen, job=None) -> None:
    if os.name == "nt":
        if job:
            job.close()
        elif proc.poll() is None:
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def execute(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    log_dir: Path,
    timeout: float,
    check_control: Callable[[], None],
    on_line: Callable[[str], None] | None = None,
    stdin: str | None = None,
    max_bytes: int = 20000000,
) -> tuple[int, str, str]:
    """Drain both pipes, bound time/output, and terminate the whole process tree."""
    log_dir.mkdir(parents=True, exist_ok=True)
    kwargs = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs,
        )
    except OSError as exc:
        raise StartupError(f"cannot start {Path(argv[0]).name}: {exc}") from exc
    job = None
    if os.name == "nt":
        from hx.windows import Job

        try:
            job = Job(int(proc._handle))
        except OSError as exc:
            proc.kill()
            proc.wait(timeout=5)
            raise StartupError(f"cannot attach process to a Windows Job Object: {exc}") from exc
    errors: list[Exception] = []
    output: dict[str, list[str]] = {"stdout": [], "stderr": []}
    total_bytes = 0
    guard = threading.Lock()

    def drain(name: str, pipe):
        nonlocal total_bytes
        with (log_dir / f"{name}.txt").open("wb") as stream:
            try:
                # Bound even a malformed stream containing no newline.
                while chunk := pipe.readline(65536):
                    with guard:
                        total_bytes += len(chunk)
                        if total_bytes > max_bytes:
                            raise HXError("process log budget exceeded")
                    stream.write(chunk)
                    stream.flush()
                    line = chunk.decode("utf-8", errors="replace")
                    output[name].append(line)
                    if name == "stdout" and on_line:
                        on_line(line)
            except Exception as exc:
                errors.append(exc)
            finally:
                pipe.close()

    readers = [
        threading.Thread(target=drain, args=("stdout", proc.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", proc.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    started = time.monotonic()
    try:
        if stdin:
            # Prompts are bounded by contracts; pipe writes get their own thread so timeout still works.
            def feed():
                try:
                    proc.stdin.write(stdin.encode())
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            threading.Thread(target=feed, daemon=True).start()
        while proc.poll() is None:
            check_control()
            if errors:
                raise errors[0]
            if time.monotonic() - started > timeout:
                raise ProcessTimeout(f"process timed out after {timeout:g}s")
            time.sleep(0.05)
        # Reap background descendants even if the root process exits normally.
        kill_tree(proc, job)
        for reader in readers:
            reader.join(timeout=5)
        if errors:
            raise errors[0]
        if any(reader.is_alive() for reader in readers):
            raise HXError("child process left an output pipe open")
        check_control()
        return proc.returncode, "".join(output["stdout"]), "".join(output["stderr"])
    finally:
        kill_tree(proc, job)
        for reader in readers:
            reader.join(timeout=5)
