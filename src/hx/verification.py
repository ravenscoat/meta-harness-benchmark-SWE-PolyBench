from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from hx.check_execution import command_check
from hx.git import assert_clean, clone, git
from hx.models import Candidate, Check, ProcessTimeout, Settings, Task, Verification
from hx.process import clean_env, execute


class Verifier:
    version = "verify@2"

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(
        self,
        candidate: Candidate,
        task: Task,
        directory: Path,
        check_control: Callable[[], None],
        emit: Callable[[str, dict], None],
    ) -> Verification:
        if task.frontend:
            from hx.challenge_eval import FullstackVerifier

            return FullstackVerifier(self.settings).run(
                candidate, task, directory, check_control, emit
            )
        repo = clone(Path(candidate.workspace), directory / "workspace", candidate.candidate_commit)
        check_control()
        checks: list[Check] = []
        for file in candidate.changed_files:
            path = repo / file
            if file.endswith(".py") and path.exists():
                try:
                    compile(path.read_bytes(), file, "exec")
                    checks.append(
                        Check(name="compile:" + file, passed=True, evidence="Python syntax valid")
                    )
                except (SyntaxError, ValueError) as exc:
                    checks.append(Check(name="compile:" + file, passed=False, evidence=str(exc)))
        temp = directory / "tmp"
        temp.mkdir()
        env = clean_env(
            {
                "PYTHONPATH": str(repo),
                "HX_DB": str(directory / "app.sqlite3"),
                "TMP": str(temp),
                "TEMP": str(temp),
                "TMPDIR": str(temp),
            }
        )
        module, symbol = task.app_module.split(":")
        commands = [
            (
                "import_app",
                [
                    sys.executable,
                    "-c",
                    f"import importlib; m=importlib.import_module({module!r}); assert hasattr(m, {symbol!r})",
                ],
            ),
            (
                "visible_tests",
                [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    "--source",
                    "backend",
                    "--data-file",
                    str(directory / ".coverage"),
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    *task.test_paths,
                ],
            ),
        ]
        for name, command in commands:
            checks.append(command_check(
                name, command, repo, env, directory / name,
                self.settings, check_control, emit,
            ))
        try:
            coverage_value = self._coverage(candidate, repo, directory, env, check_control)
        except ProcessTimeout:
            check_control()
            coverage_value = None
        gaps = []
        if coverage_value is None:
            gaps.append("changed-line coverage unavailable")
        elif coverage_value < 1.0:
            gaps.append(
                f"changed executable lines exercised: {coverage_value:.0%}; coverage is not proof of behavior"
            )
        if task.acceptance:
            # Only a pass/fail summary leaves this evaluator. Full diagnostic output is evaluator-only.
            from hx.acceptance import program

            code, _, _ = execute(
                [sys.executable, "-c", program(task.acceptance)],
                repo,
                clean_env(
                    {
                        "PYTHONPATH": str(repo),
                        "HX_DB": str(directory / "acceptance.sqlite3"),
                        "TMP": str(temp),
                        "TEMP": str(temp),
                        "TMPDIR": str(temp),
                    }
                ),
                directory / "private_acceptance",
                self.settings.verification_timeout_seconds,
                check_control,
                max_bytes=self.settings.max_log_bytes,
            )
            checks.append(
                Check(
                    name="acceptance",
                    passed=code == 0,
                    evidence="acceptance passed" if code == 0 else "acceptance failed",
                )
            )
        else:
            gaps.append("no independent acceptance check configured for this task")
        assert_clean(repo, candidate.candidate_commit)
        return Verification(
            candidate_commit=candidate.candidate_commit,
            passed=all(check.passed for check in checks),
            checks=checks,
            changed_line_coverage=coverage_value,
            known_gaps=gaps,
        )

    def _coverage(
        self,
        candidate: Candidate,
        repo: Path,
        directory: Path,
        env: dict,
        check_control: Callable[[], None],
    ) -> float | None:
        output = directory / "coverage.json"
        code, _, _ = execute(
            [
                sys.executable,
                "-m",
                "coverage",
                "json",
                "--data-file",
                str(directory / ".coverage"),
                "-o",
                str(output),
            ],
            repo,
            env,
            directory / "coverage_report",
            self.settings.verification_timeout_seconds,
            check_control,
            max_bytes=self.settings.max_log_bytes,
        )
        if code or not output.exists():
            return None
        data = json.loads(output.read_text("utf-8"))
        # coverage.py uses native separators; Git paths are always POSIX-style.
        reports = {path.replace("\\", "/"): report for path, report in data["files"].items()}
        executed, total = 0, 0
        diff = git(
            repo,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--unified=0",
            candidate.base_commit,
            candidate.candidate_commit,
            "--",
            "backend",
        )
        file = None
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                file = line[6:]
            elif line.startswith("@@") and file:
                match = re.search(r"\+(\d+)(?:,(\d+))?", line)
                if not match:
                    continue
                start = int(match[1])
                count = int(match[2]) if match[2] is not None else 1
                report = reports.get(file, {})
                hit = set(report.get("executed_lines", []))
                statements = hit | set(report.get("missing_lines", []))
                changed = set(range(start, start + count)) & statements
                executed += len(changed & hit)
                total += len(changed)
        return executed / total if total else None
