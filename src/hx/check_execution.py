"""Recover command timeouts without masking cancellation or evidence violations."""

from pathlib import Path

from hx.failure_evidence import focused_output
from hx.models import Check, ProcessTimeout
from hx.process import execute


def log_tail(directory: Path, limit: int = 2500) -> str:
    chunks = []
    for name in ("stdout.txt", "stderr.txt"):
        path = directory / name
        if path.exists():
            with path.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - limit))
                chunks.append(f"{name}: " + stream.read().decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def command_check(name, command, cwd, env, logs, settings, control, emit) -> Check:
    emit("verification.started", {"name": name, "timeout_seconds": settings.verification_timeout_seconds})
    try:
        code, out, err = execute(
            command, cwd, env, logs, settings.verification_timeout_seconds, control,
            max_bytes=settings.max_log_bytes,
        )
        check = Check(name=name, passed=code == 0,
                      evidence=(out + err)[-6000:] if code == 0 and (out or err) else
                      focused_output(out + err, 6000) or ("passed" if code == 0 else f"exit {code}"))
    except ProcessTimeout as exc:
        # execute has already killed the child tree. A global limit still aborts.
        control()
        check = Check(name=name, passed=False, evidence=(
            f"{exc}. Child tree terminated. Inspect the last test/command output before retrying; "
            "check hanging awaits, effect-driven render loops and unstable test inputs.\n"
            + log_tail(logs)
        ))
        emit("verification.timeout", {"name": name, "logs": str(logs)})
    emit("verification.check", {"name": name, "passed": check.passed})
    return check
