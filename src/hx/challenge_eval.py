from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from hx.challenge_checks import backend_program, frontend_program
from hx.challenge_suite import ASSETS
from hx.check_execution import command_check
from hx.git import assert_clean, clone
from hx.models import Candidate, Settings, Task, Verification
from hx.process import clean_env, execute


def npm_command(*args: str) -> list[str]:
    # Avoid shell interpretation and PowerShell npm.ps1 execution policies.
    node = shutil.which("node")
    npm = (shutil.which("npm.cmd") or shutil.which("npm")) if os.name == "nt" else shutil.which("npm")
    if not node or not npm:
        raise RuntimeError("Node.js/npm are required for the React benchmark")
    cli = Path(node).parent / "node_modules/npm/bin/npm-cli.js"
    if not cli.exists() and Path(npm).resolve().name == "npm-cli.js":
        # Debian/Ubuntu place the actual JS entrypoint under /usr/share/nodejs.
        cli = Path(npm).resolve()
    if not cli.exists():
        raise RuntimeError("npm CLI entrypoint unavailable beside Node.js")
    return [node, str(cli), *args]


def prepare_frontend(repo: Path, logs: Path, control=lambda: None):
    if (repo / "frontend/node_modules/vitest/vitest.mjs").exists():
        return
    cache = ASSETS.parent / ".hx/npm-cache"
    code, _, err = execute(
        npm_command(
            "ci", "--offline", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", str(cache)
        ),
        repo / "frontend",
        clean_env(),
        logs,
        90,
        control,
    )
    if code:
        raise RuntimeError("offline frontend dependency setup failed: " + err[-1500:])


class FullstackVerifier:
    version = "fullstack-visible@2"

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, candidate: Candidate, task: Task, directory: Path, check_control, emit):
        repo = clone(Path(candidate.workspace), directory / "workspace", candidate.candidate_commit)
        prepare_frontend(repo, directory / "dependencies", check_control)
        temp = directory / "tmp"
        temp.mkdir()
        env = clean_env(
            {
                "PYTHONPATH": str(repo),
                "HX_DB": str(directory / "visible.sqlite3"),
                "TMP": str(temp),
                "TEMP": str(temp),
            }
        )
        commands = [
            (
                "backend_tests",
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                repo,
            ),
            ("react_tests", npm_command("test", "--", "--maxWorkers=1"), repo / "frontend"),
            ("react_build", npm_command("run", "build"), repo / "frontend"),
        ]
        checks = []
        for name, command, cwd in commands:
            checks.append(command_check(
                name, command, cwd, env, directory / name,
                self.settings, check_control, emit,
            ))
        assert_clean(repo, candidate.candidate_commit)
        return Verification(
            candidate_commit=candidate.candidate_commit,
            passed=all(c.passed for c in checks),
            checks=checks,
            changed_line_coverage=None,
            known_gaps=[
                "Independent benchmark acceptance is evaluated after this workflow; visible tests alone do not establish benchmark success."
            ],
        )


def grade(candidate: Candidate, groups: list[str], directory: Path, settings: Settings) -> dict:
    """Keep private diagnostics separate from worker/proposer artifacts; expose group scores."""
    repo = clone(Path(candidate.workspace), directory / "workspace", candidate.candidate_commit)
    prepare_frontend(repo, directory / "dependencies")
    temp = directory / "tmp"
    temp.mkdir()
    results = {}
    for group in groups:
        if group in {"search", "board", "editor"}:
            private = repo / "frontend/__hx_acceptance.test.jsx"
            private.write_text(frontend_program([group]), "utf-8")
            try:
                code, _, _ = execute(
                    npm_command(
                        "exec", "--", "vitest", "run", "__hx_acceptance.test.jsx", "--maxWorkers=1"
                    ),
                    repo / "frontend",
                    clean_env({"TMP": str(temp), "TEMP": str(temp)}),
                    directory / group,
                    settings.verification_timeout_seconds,
                    lambda: None,
                )
            finally:
                private.unlink(missing_ok=True)
        else:
            code, _, _ = execute(
                [sys.executable, "-c", backend_program([group])],
                repo,
                clean_env(
                    {
                        "PYTHONPATH": str(repo),
                        "HX_DB": str(directory / (group + ".sqlite3")),
                        "TMP": str(temp),
                        "TEMP": str(temp),
                    }
                ),
                directory / group,
                settings.verification_timeout_seconds,
                lambda: None,
            )
        results[group] = code == 0
    assert_clean(repo, candidate.candidate_commit)
    return {
        "passed": all(results.values()),
        "groups": results,
        "candidate_commit": candidate.candidate_commit,
    }
