"""Supervise a frozen campaign without changing its per-task protocol."""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from hx.config import canonical
from hx.models import HXError
from hx.process import clean_env, execute
from hx.store import atomic_write, now


class QuotaStop(HXError):
    pass


class OperatorStop(HXError):
    pass


def is_quota_error(message):
    value = str(message).lower()
    return "usage limit" in value or "rate limit" in value


def launch(argv, directory, timeout=28800):
    logs = directory.resolve() / "controller-attempts" / uuid.uuid4().hex
    started = time.monotonic()
    result = {"started": now(), "argv": argv, "logs": str(logs)}

    def event(line):
        print(line.rstrip(), flush=True)
        try:
            value = json.loads(line)
        except ValueError:
            return
        if (
            isinstance(value, dict)
            and value.get("event") == "case.finished"
            and is_quota_error(value.get("error"))
        ):
            # score.json is already saved at this event. Preserve that row and stop
            # the controller before unavailable workers contaminate further trials.
            raise QuotaStop(
                "Codex quota unavailable; recorded trial retained, further scheduling stopped"
            )
        if (
            isinstance(value, dict)
            and value.get("event") == "case.finished"
            and (directory / "stop-after-case").exists()
        ):
            raise OperatorStop(
                "Operator requested a stop at a scored case boundary; recorded results retained"
            )

    extra = {"CODEX_HOME": os.environ["CODEX_HOME"]} if os.environ.get("CODEX_HOME") else {}
    try:
        code, _, stderr = execute(
            argv, Path.cwd(), clean_env(extra), logs, timeout, lambda: None, event
        )
        result.update(
            status="completed"
            if code == 0
            else "quota_stop"
            if is_quota_error(stderr)
            else "failed",
            exit_code=code,
        )
        if stderr:
            print(stderr[-3000:], file=sys.stderr, flush=True)
    except HXError as error:
        result.update(
            status="quota_stop"
            if isinstance(error, QuotaStop)
            else "operator_stop"
            if isinstance(error, OperatorStop)
            else "failed",
            error=str(error),
        )
    finally:
        result["seconds"] = time.monotonic() - started
        result["finished"] = now()
        atomic_write(logs / "supervisor.json", canonical(result))
    print(json.dumps({"event": "supervisor.finished", **result}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=28800)
    parser.add_argument("directory", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply Python arguments after --")
    result = launch([sys.executable, *command], args.directory, args.timeout)
    return (
        0
        if result["status"] == "completed"
        else 75
        if result["status"] in {"quota_stop", "operator_stop"}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
