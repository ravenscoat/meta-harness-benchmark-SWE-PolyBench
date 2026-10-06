"""Evaluate a complete logged code patch from an interrupted proposal; no models."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hx.code_search import (
    TARGET,
    dominates,
    evaluate,
    frontier,
    seal,
    search_cases,
    sha,
    validation_cases,
)
from hx.config import canonical
from hx.git import git
from hx.models import HXError
from hx.store import atomic_write
from scripts.code_search_history import read
from scripts.run_code_search import GATES, copy_gate_dependencies


def logged_patch(stdout: Path) -> bytes:
    patches = []
    for line in stdout.read_text().splitlines():
        item = json.loads(line).get("item", {})
        if item.get("type") != "command_execution" or item.get("status") != "completed":
            continue
        output = item.get("aggregated_output", "")
        start = output.find("diff --git a/" + TARGET + " b/" + TARGET + "\n")
        if start < 0:
            continue
        rows = output[start:].splitlines(True)
        kept = []
        for row in rows:
            if row.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@ ", " ", "+", "-", "\\")):
                kept.append(row)
            else:
                break
        patches.append("".join(kept).encode())
    if not patches:
        raise HXError("No complete logged target patch; no recovery")
    patch = patches[-1]
    if patch.count(b"diff --git ") != 1:
        raise HXError("Logged draft touches more than the permitted target")
    return patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    original, root = args.original.resolve(), args.root.resolve()
    original_lock = (original / "archive-lock.json").read_bytes()
    read(original)
    if root.exists():
        raise HXError("New recovery identity required")
    root.mkdir(parents=True)
    project = Path.cwd()
    try:
        baseline = (original / "incumbent.py").read_bytes()
        if (project / TARGET).read_bytes() != baseline:
            raise HXError("Live incumbent differs from interrupted attempt")
        patch = logged_patch(original / "sol/stdout.txt")
        atomic_write(root / "delivery.patch", patch)
        atomic_write(root / "incumbent.py", baseline)
        with tempfile.TemporaryDirectory(prefix="hx-code-recovery-",
                dir="/opt/hx-polybench-runtime/v1/infra-checks") as temp:
            workspace = Path(temp) / "workspace"
            shutil.copytree(project / "src", workspace / "src", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copyfile(project / "pyproject.toml", workspace / "pyproject.toml")
            tests = workspace / "tests"
            tests.mkdir()
            for name in [*GATES, "conftest.py", "test_code_search.py"]:
                shutil.copyfile(project / "tests" / name, tests / name)
            copy_gate_dependencies(project, workspace)
            git(workspace, "init")
            replay = subprocess.run(["git", "-C", str(workspace), "apply", "--check", "-"],
                input=patch, capture_output=True, timeout=15)
            if replay.returncode:
                raise HXError("Logged draft patch cannot replay exactly")
            replay = subprocess.run(["git", "-C", str(workspace), "apply", "-"],
                input=patch, capture_output=True, check=True, timeout=15)
            candidate = workspace / TARGET
            atomic_write(root / "candidate.py", candidate.read_bytes())
            before = evaluate(root / "incumbent.py", search_cases(), root / "incumbent-search")
            after = evaluate(candidate, search_cases(), root / "candidate-search")
            validation_before = evaluate(root / "incumbent.py", validation_cases(), root / "incumbent-validation")
            validation_after = evaluate(candidate, validation_cases(), root / "candidate-validation")
            gate = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                *["tests/" + name for name in [*GATES, "test_code_search.py"]],
                "--basetemp=" + str(Path(temp) / "pytest")], cwd=workspace, capture_output=True,
                timeout=180, env={k: v for k, v in os.environ.items() if k != "CODEX_HOME"})
            atomic_write(root / "regressions.stdout.txt", gate.stdout)
            atomic_write(root / "regressions.stderr.txt", gate.stderr)
            adopted = (not gate.returncode and dominates(after, before) and
                validation_after["quality"] >= validation_before["quality"])
            if (original / "archive-lock.json").read_bytes() != original_lock or (project / TARGET).read_bytes() != baseline:
                raise HXError("Source or original archive changed during recovery")
            if adopted:
                atomic_write(project / TARGET, candidate.read_bytes())
            atomic_write(root / "frontier.json", canonical({"candidates": frontier({"incumbent": before, "candidate": after})}))
            atomic_write(root / "adoption.json", canonical({"adopted": adopted, "model_calls": 0,
                "original_outcome": "failed", "original_archive_sha256": sha(original_lock),
                "trace_sha256": sha((original / "sol/stdout.txt").read_bytes()),
                "candidate_sha256": sha(candidate.read_bytes()), "regressions_passed": not gate.returncode,
                "limitations": "Model-free draft recovery. Original timeout remains failed; model usage was not reported. No coding benchmark claim."}))
    except Exception as exc:
        atomic_write(root / "failure.json", canonical({"error": str(exc), "adopted": False, "model_calls": 0}))
        raise
    finally:
        atomic_write(root / "archive-lock.json", canonical({"files": seal(root)}))
    print(json.dumps({"adopted": adopted, "model_calls": 0, "root": str(root)}))


if __name__ == "__main__":
    main()
