"""One cheap Sol code candidate, external evaluation, archive and gated adoption.

Run under native WSL Python. Each root is a new identity; history is explicit.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from benchmarks.polybench.runner import AUTH, BINARY
from hx.adapters import CodexAdapter
from hx.code_search import (
    TARGET,
    CodeProposal,
    copy_experience,
    dominates,
    evaluate,
    frontier,
    seal,
    search_cases,
    sha,
    validate_source,
    validation_cases,
)
from hx.config import canonical, load_settings
from hx.git import git
from hx.models import HXError, ProcessTimeout, Task
from hx.store import atomic_write
from scripts.overnight_limits import account_usage, can_start

GATES = ["test_meta.py", "test_candidate_budget.py", "test_single_workflow.py",
    "test_completed_timeout.py"]
ACTIVE_ROOT = None


def recover_interrupted(root: Path):
    # Original failure is sealed before this separate zero-model-call identity.
    recovery = root.with_name(root.name + "-recovery")
    return subprocess.run([sys.executable, "-m", "scripts.recover_code_search", str(root),
        str(recovery)], timeout=240, check=False).returncode


def copy_gate_dependencies(project, workspace):
    # Runner-shape validation only; never copy grader files or private patches.
    destination = workspace / "benchmarks/polybench"
    destination.mkdir(parents=True)
    for path in ["benchmarks/__init__.py", "benchmarks/polybench/__init__.py",
            "benchmarks/polybench/public_checks.py"]:
        source = project / path
        target = workspace / path
        if source.exists():
            shutil.copyfile(source, target)
        else:
            target.touch()


def public_sources(project):
    sources = {}
    # Full, explicitly public local worker artifacts. Never import benchmark
    # grading directories, acceptance traces, .git, effective config or auth.
    live = project / ".hx/single-luna-live-v1"
    for path in live.glob("runs/*/steps/implement/attempt-1/*"):
        if path.name in {"stdout.txt", "stderr.txt", "prompt.txt", "result.json"}:
            sources["local-luna/" + path.name] = path
    for name in ("meta-single-v2", "meta-single-v3", "meta-single-v4"):
        for path in (project / ".hx" / name).glob("attempt-1/sol/*"):
            if path.name in {"stdout.txt", "stderr.txt", "prompt.txt", "result.json"}:
                sources[name + "/" + path.name] = path
    return sources


def main():
    global ACTIVE_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--history", type=Path, action="append", default=[])
    parser.add_argument("--surface", choices=["evidence", "worker-loop"], default="evidence")
    parser.add_argument("--finalize-loop", type=Path)
    args = parser.parse_args()
    if args.surface == "worker-loop":
        from scripts.worker_scaffold_search import finalize_recovered_candidate, run
        if args.finalize_loop:
            finalize_recovered_candidate(args.finalize_loop, args.root)
        else:
            run(args.root, args.history)
        return
    if args.finalize_loop:
        raise HXError("--finalize-loop requires --surface worker-loop")
    project = Path.cwd().resolve()
    root = args.root.resolve()
    if root.exists():
        raise HXError("New attempt root required; previous outcomes never overwritten")
    root.mkdir(parents=True)
    ACTIVE_ROOT = root
    usage = 0
    start = time.monotonic()
    try:
        quota = account_usage(BINARY, AUTH)
        atomic_write(root / "quota.json", canonical(quota))
        if not can_start(quota):
            raise HXError("Account quota does not allow model work")
        with tempfile.TemporaryDirectory(prefix="hx-code-search-",
                dir="/opt/hx-polybench-runtime/v1/infra-checks") as temporary:
            native = Path(temporary)
            workspace = native / "workspace"
            workspace.mkdir()
            shutil.copytree(project / "src", workspace / "src",
                ignore=shutil.ignore_patterns("__pycache__", "code_search.py"))
            shutil.copytree(workspace / "src", root / "runtime-source")
            tests = workspace / "tests"
            tests.mkdir()
            for name in GATES:
                shutil.copyfile(project / "tests" / name, tests / name)
            shutil.copyfile(project / "tests/conftest.py", tests / "conftest.py")
            copy_gate_dependencies(project, workspace)
            for name in ("pyproject.toml", "hx.toml"):
                shutil.copyfile(project / name, workspace / name)
            experience = copy_experience(workspace / "experience", public_sources(project))
            copy_experience(root / "experience", public_sources(project))
            for index, old in enumerate(args.history):
                # Only previous code-search artifacts sealed by this runner.
                lock = json.loads((old / "archive-lock.json").read_text())
                paths = lock["files"]
                for name, expected in paths.items():
                    path = old / name
                    if name.startswith("/") or ".." in Path(name).parts or path.is_symlink():
                        raise HXError("Invalid history archive entry")
                    if sha(path.read_bytes()) != expected:
                        raise HXError("History archive changed")
                public = {n: old / n for n in paths if n in {"candidate.py", "incumbent.py",
                    "proposal.json", "failure.json", "proposer-instructions.txt", "events.jsonl"}
                    or n.startswith(("sol/", "incumbent-search/", "candidate-search/"))}
                copy_experience(workspace / "history" / str(index), public)
            baseline = (project / TARGET).read_bytes()
            baseline_path = workspace / TARGET
            atomic_write(root / "incumbent.py", baseline)
            baseline_score = evaluate(baseline_path, search_cases(), root / "incumbent-search")
            atomic_write(workspace / "search-cases.json", canonical(search_cases()))
            atomic_write(workspace / "incumbent-score.json", canonical(baseline_score))
            git(workspace, "init")
            git(workspace, "add", ".")
            git(workspace, "-c", "user.name=HX", "-c", "user.email=hx@local", "commit", "-qm", "Search incumbent")
            before = seal(workspace)
            # Git internals are mutable bookkeeping; all other input files protected.
            before = {n: h for n, h in before.items() if not n.startswith(".git/")}
            settings = load_settings(project / "hx.toml").model_copy(update={"worker_model": "gpt-6.1-sol"})
            def control():
                if time.monotonic() - start > 240 or usage > 30000:
                    raise HXError("Code search proposal budget exhausted")
            def emit(kind, data):
                nonlocal usage
                if kind == "worker.usage":
                    usage += int(data["tokens"])
                with (root / "events.jsonl").open("ab") as stream:
                    stream.write(canonical({"kind": kind, "data": data}) + b"\n")
                atomic_write(root / "usage.json", canonical({"reported_tokens": usage, "limit": 30000}))
            instructions = (
                "You are Sol, the outer coding meta-harness. Read filesystem experience/ and history/ "
                "selectively with rg/cat, inspect source and prior traces. Diagnose mechanisms, then write "
                "one improved executable failure-evidence extraction algorithm in src/hx/failure_evidence.py. "
                "Preserve focused_output(output: str, limit: int=2000)->str. Only this file may change. "
                "Keep output bounded, retain actual error/cause lines despite warning noise, avoid redundant "
                "context. Search cases/score are diagnostic mechanism objectives, NOT coding scores. "
                "Optimize quality then excerpt size; never hard-code cases, messages, filenames or answers. "
                "Only import re; pure functions and standard string/list/set/dict operations, no IO, reflection, "
                "dunder names, classes, decorators or dynamic code. You may freely rewrite the algorithm. "
                "Do not change tests, history, experience, models, budgets, configuration or evaluator. "
                "Do not run models, network, Python or tests in this workspace; read/edit only. "
                "Independent runner evaluates after your turn, to avoid touching protected input files. "
                "Return diagnosis, inspected_files (real relative files you read), change, limitations."
            )
            atomic_write(root / "proposer-instructions.txt", instructions.encode())
            home = native / "auth"
            home.mkdir()
            shutil.copyfile(AUTH, home / "auth.json")
            (home / "auth.json").chmod(0o600)
            old_path, old_home = os.environ.get("PATH", ""), os.environ.get("CODEX_HOME")
            os.environ["PATH"] = str(BINARY.parent) + os.pathsep + old_path
            os.environ["CODEX_HOME"] = str(home)
            try:
                raw = CodexAdapter(settings).run("implementer", Task(id="sol-code-search", repo=str(workspace),
                    report="Improve evidence extraction from observed public harness failures."), workspace,
                    {"history_directory": "history/", "public_experience": "experience/",
                     "source_file": TARGET, "search_score": baseline_score}, instructions,
                    CodeProposal, root / "sol", control, emit, 180)
            finally:
                os.environ["PATH"] = old_path
                if old_home is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_home
                shutil.rmtree(home)
            proposal = CodeProposal.model_validate(raw)
            atomic_write(root / "proposal.json", canonical(proposal.model_dump()))
            control()
            after = {n: h for n, h in seal(workspace).items() if not n.startswith(".git/")}
            changed = {n for n in set(before) | set(after) if before.get(n) != after.get(n)}
            candidate = baseline_path.read_bytes()
            atomic_write(root / "candidate.py", candidate)
            if changed != {TARGET} or git(workspace, "remote"):
                raise HXError("Candidate changed protected inputs or made no code change")
            if not all(name in before for name in proposal.inspected_files):
                raise HXError("Proposal named files outside supplied experience")
            validate_source(candidate)
            candidate_score = evaluate(baseline_path, search_cases(), root / "candidate-search")
            # Holdout mechanism evidence is outside proposer workspace and not used
            # for another proposal in this invocation.
            incumbent_validation = evaluate(root / "incumbent.py", validation_cases(), root / "incumbent-validation")
            candidate_validation = evaluate(root / "candidate.py", validation_cases(), root / "candidate-validation")
            regression = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                *["tests/" + n for n in GATES], "--basetemp=" + str(native / "pytest")], cwd=workspace,
                capture_output=True, timeout=180, env={k: v for k, v in os.environ.items() if k != "CODEX_HOME"})
            atomic_write(root / "regressions.stdout.txt", regression.stdout)
            atomic_write(root / "regressions.stderr.txt", regression.stderr)
            adoption = (not regression.returncode and dominates(candidate_score, baseline_score) and
                candidate_validation["quality"] >= incumbent_validation["quality"])
            atomic_write(root / "frontier.json", canonical({"candidates": frontier({"incumbent": baseline_score,
                "candidate": candidate_score}), "metric": baseline_score["metric"]}))
            if (project / TARGET).read_bytes() != baseline:
                raise HXError("Live incumbent changed during search")
            if adoption:
                atomic_write(project / TARGET, candidate)
            atomic_write(root / "adoption.json", canonical({"adopted": adoption,
                "source_sha256": sha(candidate), "incumbent_sha256": sha(baseline),
                "regressions_passed": not regression.returncode, "reported_tokens": usage,
                "limitations": "Pure evidence-tool search. No new Luna coding task or general solve-rate evidence."}))
            atomic_write(root / "experience-lock.json", canonical(experience))
    except Exception as exc:
        atomic_write(root / "failure.json", canonical({"error": str(exc), "reported_tokens": usage,
            "usage_complete": usage > 0, "adopted": False}))
        raise
    finally:
        # Preserve every outcome, including malformed proposals and failed gates.
        atomic_write(root / "archive-lock.json", canonical({"files": seal(root),
            "seconds": time.monotonic() - start}))
    print(json.dumps({"root": str(root), "reported_tokens": usage, "adopted": adoption}))


if __name__ == "__main__":
    try:
        main()
    except ProcessTimeout:
        if ACTIVE_ROOT is None:
            raise
        raise SystemExit(recover_interrupted(ACTIVE_ROOT)) from None
