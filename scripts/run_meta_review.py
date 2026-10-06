"""One bounded Sol proposal, regression gate, fixture run and automatic adoption."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from benchmarks.polybench.runner import AUTH, BINARY
from hx.adapters import FakeAdapter
from hx.config import canonical, load_settings, load_task
from hx.demo import initialize
from hx.engine import Engine
from hx.meta import candidate_settings, export_public_runs, propose, public_evidence, settings_toml
from hx.store import Store, atomic_write
from scripts.overnight_limits import account_usage, can_start

ACTIVE_ROOT = None


def main():
    global ACTIVE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--evidence", type=Path)
    source.add_argument("--state-dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("hx.toml"))
    parser.add_argument("--public-outcomes", type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.config = args.config.resolve()
    if args.root.exists():
        raise RuntimeError("Use a new meta attempt root; previous outcomes are immutable")
    args.root.mkdir(parents=True)
    ACTIVE_ROOT = args.root
    original = args.config.read_bytes()
    settings = load_settings(args.config)
    atomic_write(args.root / "config.before.toml", original)
    if args.state_dir:
        if not (args.state_dir / "state.sqlite3").exists():
            raise RuntimeError("Existing native run store required")
        exported = export_public_runs(Store(args.state_dir))
        args.evidence = args.root / "public-runs.json"
        atomic_write(args.evidence, canonical(exported))
    usage = account_usage(BINARY, AUTH)
    atomic_write(args.root / "quota.json", canonical(usage))
    if not can_start(usage):
        raise RuntimeError("Account quota does not permit model work; no reset credits used")
    evidence = public_evidence(args.evidence)
    if args.public_outcomes:
        rows = json.loads(args.public_outcomes.read_text())["rows"]
        # Only public workflow metadata, never scorer patches, commands or test logs.
        evidence["workflow_outcomes"] = [{"case": r["case"], "status": r["status"],
            "tokens": r["observed_tokens"], "error": r.get("error")}
            for r in rows[:30]]
    evidence["current_mechanisms"] = [
        "Single Luna; model reviews removed. Repository map automatically supplied.",
        "Completed candidates preserved and verified after final-turn token overshoot; new calls blocked without headroom.",
        "Failure excerpts prioritize traceback/error lines before warning noise. Full logs retained.",
        "Installed Mocha/Jest/Vitest accepted; public patch application checked before tests.",
        "Proposal feedback numeric value must agree with rationale; prior incompatible rationale was rolled back.",
    ]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="hx-meta-auth-",
            dir="/opt/hx-polybench-runtime/v1/infra-checks") as auth_home:
        auth_target = Path(auth_home) / "auth.json"
        shutil.copyfile(AUTH, auth_target)
        auth_target.chmod(0o600)
        old_path, old_home = os.environ.get("PATH", ""), os.environ.get("CODEX_HOME")
        os.environ["PATH"] = str(BINARY.parent) + os.pathsep + old_path
        os.environ["CODEX_HOME"] = auth_home
        try:
            proposal = propose(evidence, args.root / "attempt-1", settings)
        finally:
            os.environ["PATH"] = old_path
            if old_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_home
    candidate = candidate_settings(settings, proposal)
    atomic_write(args.root / "config.candidate.toml", settings_toml(candidate))
    with tempfile.TemporaryDirectory(prefix="hx-meta-gates-", dir="/opt/hx-polybench-runtime/v1/infra-checks") as temp:
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "tests/test_meta.py", "tests/test_candidate_budget.py", "tests/test_single_workflow.py",
            "tests/test_polybench_public_checks.py", "tests/test_test_plan_revision.py",
            "--basetemp=" + str(Path(temp) / "pytest")], capture_output=True, timeout=180)
        atomic_write(args.root / "regressions.stdout.txt", result.stdout)
        atomic_write(args.root / "regressions.stderr.txt", result.stderr)
        if result.returncode:
            raise RuntimeError("Regression gate failed; proposal not adopted")
        paths = initialize(Path(temp) / "fixture")
        fixture_settings = candidate.model_copy(update={"adapter": "fake"})
        adapter = FakeAdapter()
        engine = Engine(Store(Path(temp) / "state"), fixture_settings, adapter)
        # This gate validates chosen knobs with actual FastAPI execution, not model ability.
        run = engine.create(load_task(paths[0]))
        outcome = engine.execute(run["id"])
        atomic_write(args.root / "fixture.json", canonical({
            "status": outcome["status"], "handoff": outcome["handoff"],
            "worker_calls": adapter.calls, "error": outcome["error"],
            "limitation": "Scripted fixture validates mechanisms, not solve-rate improvement."}))
        if outcome["status"] != "ready_for_approval" or adapter.calls != {"implementer": 1}:
            raise RuntimeError("Candidate configuration fixture failed; not adopted")
    if args.config.read_bytes() != original:
        raise RuntimeError("Configuration changed during meta attempt; not adopted")
    proposed = settings_toml(candidate)
    atomic_write(args.config, proposed)
    atomic_write(args.root / "adoption.json", canonical({
        "adopted": True, "model": "gpt-6.1-sol", "workers": "gpt-6-luna",
        "regressions_passed": True, "fixture_passed": True,
        "config_sha256": hashlib.sha256(proposed).hexdigest(),
        "seconds": time.monotonic() - started,
        "limitations": "Configuration regression acceptance is not evidence of better coding performance. No historical trial rerun."}))
    print(json.dumps({"adopted": True, "root": str(args.root), "proposal": proposal.name}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if ACTIVE_ROOT is not None:
            atomic_write(ACTIVE_ROOT / "failure.json", canonical({"error": str(exc),
                "adopted": False}))
        print(f"Meta attempt stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
