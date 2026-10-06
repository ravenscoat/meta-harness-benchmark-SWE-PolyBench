from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from hx.config import load_settings, load_task
from hx.engine import Engine
from hx.models import HXError
from hx.store import Store


def print_run(run: dict) -> None:
    handoff = run.get("handoff") or {}
    print(
        json.dumps(
            {
                "run_id": run["id"],
                "status": run["status"],
                "candidate_commit": handoff.get("candidate_commit"),
                "verified": handoff.get("verified"),
                "reviewed": handoff.get("reviewed"),
                "approval": run.get("decision") or "pending",
                "error": run.get("error"),
            },
            indent=2,
        )
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="hx", description="Local evidence-gated Codex workflow")
    result.add_argument("--state-dir", type=Path, default=Path(".hx"))
    result.add_argument("--config", type=Path, default=Path("hx.toml"))
    commands = result.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="create a target app and five task specs")
    demo.add_argument("directory", type=Path, nargs="?", default=Path(".hx/demo"))
    run = commands.add_parser("run", help="run one task to a human handoff")
    run.add_argument("task", type=Path)
    run.add_argument("--adapter", choices=["codex", "fake"])
    resume = commands.add_parser("resume", help="reuse sealed results and retry unfinished steps")
    resume.add_argument("run_id")
    resume.add_argument("--adapter", choices=["codex", "fake"])
    status = commands.add_parser("status")
    status.add_argument("run_id")
    status.add_argument("--full", action="store_true")
    commands.add_parser("list")
    events = commands.add_parser("events")
    events.add_argument("run_id")
    events.add_argument("--follow", action="store_true")
    cancel = commands.add_parser("cancel")
    cancel.add_argument("run_id")
    for name in ("approve", "deny"):
        command = commands.add_parser(name)
        command.add_argument("run_id")
        command.add_argument("--commit", required=True)
        command.add_argument("--reason", default="")
    commands.add_parser("doctor", help="check local CLI capabilities without making model calls")
    serve = commands.add_parser("serve", help="serve the local backend API")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--adapter", choices=["codex", "fake"])
    bench = commands.add_parser("benchmark", help="measure full workflow on supplied task specs")
    bench.add_argument("tasks", type=Path)
    bench.add_argument("--adapter", choices=["codex", "fake"], default="fake")
    bench.add_argument("--repeats", type=int, default=1, choices=range(1, 6))
    suite = commands.add_parser(
        "challenge-suite", help="materialize original hard FastAPI/React tasks"
    )
    suite.add_argument("directory", type=Path)
    validate = commands.add_parser(
        "challenge-validate", help="check seeded failures and reference solutions"
    )
    validate.add_argument("manifest", type=Path)
    validate.add_argument("directory", type=Path)
    optimize = commands.add_parser(
        "optimize", help="run baseline/full HX and bounded Sol context search"
    )
    optimize.add_argument("manifest", type=Path)
    optimize.add_argument("directory", type=Path)
    optimize.add_argument("--iterations", type=int, default=2, choices=range(1, 6))
    optimize.add_argument("--repeats", type=int, default=1, choices=range(1, 6))
    optimize.add_argument("--max-tokens", type=int, default=20000000)
    optimize.add_argument("--max-seconds", type=int, default=14400)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            executable = shutil.which("codex")
            if not executable:
                raise HXError("Codex CLI not found")
            help_text = subprocess.check_output(
                [executable, "exec", "--help"], text=True, timeout=10
            )
            required = [
                "--json",
                "--output-schema",
                "--sandbox",
                "--ignore-user-config",
                "--ephemeral",
            ]
            missing = [flag for flag in required if flag not in help_text]
            print(
                json.dumps(
                    {
                        "python": sys.executable,
                        "codex": executable,
                        "cli_version": subprocess.check_output(
                            [executable, "--version"], text=True
                        ).strip(),
                        "missing_flags": missing,
                        "models": ["gpt-6-luna", "gpt-6.1-sol"],
                        "model_access": "not tested; requires an authenticated live run",
                        "isolation": "local sandbox; not a hostile-code security boundary",
                    },
                    indent=2,
                )
            )
            return int(bool(missing))
        if args.command == "demo":
            from hx.demo import initialize

            for path in initialize(args.directory):
                print(path)
            return 0
        if args.command == "challenge-suite":
            from hx.challenge_suite import materialize

            print(materialize(args.directory))
            return 0
        store = Store(args.state_dir)
        if args.command == "status":
            run = store.get(args.run_id)
            print(
                json.dumps({**run, "steps": store.steps(args.run_id)}, indent=2)
            ) if args.full else print_run(run)
            return 0
        if args.command == "list":
            for run in store.list():
                print(f"{run['id']}  {run['status']:20}  {run['task']['id']}")
            return 0
        if args.command == "events":
            after = 0
            while True:
                for event in store.events(args.run_id, after):
                    print(json.dumps(event), flush=True)
                    after = event["seq"]
                if not args.follow or store.get(args.run_id)["status"] not in {
                    "pending",
                    "running",
                }:
                    return 0
                time.sleep(0.5)
        if args.command == "cancel":
            run = store.get(args.run_id)
            if run["status"] not in {"pending", "running"}:
                raise HXError("only pending or running tasks can be cancelled")
            store.update(args.run_id, cancel_requested=True)
            store.event(args.run_id, "cancel.requested")
            print("Cancellation requested")
            return 0
        settings = load_settings(args.config if args.config.exists() else None)
        if getattr(args, "adapter", None):
            settings = settings.model_copy(update={"adapter": args.adapter})
        if args.command == "serve":
            import uvicorn

            from hx.api import create_app

            print(f"Local API: http://127.0.0.1:{args.port}")
            print(f"Bearer token file: {store.root / 'api-token.txt'}")
            uvicorn.run(create_app(store.root, settings), host="127.0.0.1", port=args.port)
            return 0
        engine = Engine(store, settings)
        if args.command == "challenge-validate":
            from hx.challenge_validation import validate_suite

            report = validate_suite(args.manifest, args.directory, settings)
            print(json.dumps(report, indent=2))
            return 0 if report["valid"] else 1
        if args.command == "optimize":
            from hx.optimization import campaign

            if args.max_tokens < 1 or args.max_seconds < 1:
                raise HXError("campaign budgets must be positive")
            campaign(
                args.manifest,
                args.directory,
                settings,
                args.iterations,
                args.repeats,
                args.max_tokens,
                args.max_seconds,
            )
            print(args.directory.resolve() / "REPORT.md")
            return 0
        if args.command == "run":
            run = engine.create(load_task(args.task))
            print(f"Run created: {run['id']}", flush=True)
            run = engine.execute(run["id"])
            print_run(run)
            return 0 if run["status"] == "ready_for_approval" else 1
        if args.command == "resume":
            run = engine.execute(args.run_id, resume=True)
            print_run(run)
            return 0 if run["status"] == "ready_for_approval" else 1
        if args.command in {"approve", "deny"}:
            print_run(
                engine.decision(args.run_id, args.commit, args.command == "approve", args.reason)
            )
            return 0
        if args.command == "benchmark":
            from hx.benchmark import benchmark

            print(json.dumps(benchmark(engine, args.tasks, args.repeats), indent=2))
            return 0
    except (HXError, ValueError, OSError) as exc:
        print(f"HX: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Run state was saved; use hx resume RUN_ID.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
