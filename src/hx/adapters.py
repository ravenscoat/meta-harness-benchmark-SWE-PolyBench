from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from hx.config import canonical, digest
from hx.models import HXError, ProcessTimeout, Settings, StartupError, Task
from hx.process import clean_env, execute
from hx.store import atomic_write
from hx.usage import usage_breakdown


class CodexAdapter:
    name = "codex"
    capabilities = {
        "streaming": True,
        "cancel": True,
        "mid_task_resume": False,
        "pause": False,
        "structured_output": True,
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.executable = shutil.which("codex")
        if not self.executable:
            raise StartupError("Codex CLI is missing; install it and run codex login")

    def run(
        self,
        role: str,
        task: Task,
        workspace: Path,
        context: dict,
        instructions: str,
        contract: type[BaseModel],
        log_dir: Path,
        check_control: Callable[[], None],
        emit: Callable[[str, dict], None],
        timeout: float,
    ) -> dict:
        model = (
            self.settings.judgment_model if role == "consolidator" else self.settings.worker_model
        )
        schema = log_dir / "schema.json"
        result_path = log_dir / "result.json"
        log_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(schema, canonical(contract.model_json_schema()))
        prompt = (
            instructions
            + "\n\n<context>\n"
            + canonical(
                {
                    "task": {
                        "id": task.id,
                        "report": task.report,
                        "kind": task.kind,
                        "allowed_paths": task.allowed_paths,
                        "protected_paths": task.protected_paths,
                    },
                    "python_executable": sys.executable,
                    **context,
                }
            ).decode()
            + "\n</context>"
        )
        atomic_write(log_dir / "prompt.txt", prompt.encode())
        sandbox = "workspace-write" if role == "implementer" else "read-only"
        argv = [
            self.executable,
            "--no-daemon",
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--json",
            "--model",
            model,
            "--sandbox",
            sandbox,
            "-C",
            str(workspace),
            "-c",
            'approval_policy="never"',
            "-c",
            f'model_reasoning_effort="{self.settings.reasoning_effort}"',
            "-c",
            "sandbox_workspace_write.network_access=false",
            "-c",
            'web_search="disabled"',
            "--output-schema",
            str(schema),
            "-o",
            str(result_path),
            "-",
        ]
        if os.name == "nt":
            argv[3:3] = ["-c", f'windows.sandbox="{self.settings.windows_sandbox}"']
        emit(
            "worker.instantiated",
            {
                "role": role,
                "model": model,
                "sandbox": sandbox,
                "fingerprint": digest(
                    {"argv": argv[:], "prompt": prompt, "schema": contract.model_json_schema()}
                ),
            },
        )

        completed_turn = False
        def on_line(line: str):
            nonlocal completed_turn
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return
            if not isinstance(event, dict):
                return
            emit("worker.event", event)
            if event.get("type") == "turn.started":
                completed_turn = False
            if event.get("type") == "turn.failed":
                raise HXError("Codex turn failed: " + str(event.get("error", "unknown")))
            if event.get("type") == "turn.completed":
                completed_turn = True
                usage = event.get("usage", {})
                # Cached input is a subset of input; do not count it twice.
                tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                emit("worker.usage", {"tokens": tokens, "reported_usage": usage,
                                     "breakdown": usage_breakdown(usage), "role": role})

        extra = {"CODEX_HOME": os.environ["CODEX_HOME"]} if os.environ.get("CODEX_HOME") else {}
        try:
            code, _, stderr = execute(
                argv, workspace, clean_env(extra), log_dir, timeout, check_control,
                on_line, prompt, self.settings.max_log_bytes,
            )
        except ProcessTimeout:
            if not completed_turn or not result_path.exists():
                raise
            # execute already terminated the process tree. Accept only a completed,
            # schema-valid result; candidate derivation and verification still follow.
            recovered = contract.model_validate_json(result_path.read_bytes())
            emit("worker.completed_after_timeout", {"structured_result": True,
                "limitation": "CLI exit timed out after a completed turn; candidate remains unverified."})
            return recovered.model_dump()
        if code:
            raise HXError(f"Codex exited {code}: {stderr[-2000:]}")
        if not result_path.exists():
            raise HXError("Codex exited without a structured final result")
        return json.loads(result_path.read_text("utf-8"))


class FakeAdapter:
    """Scripted fixture adapter. It tests workflow behavior, never model capability."""

    name = "fake"
    capabilities = CodexAdapter.capabilities

    def __init__(self, scenario: str = "success"):
        self.scenario = scenario
        self.calls: dict[str, int] = {}
        self._lock = threading.Lock()

    def run(
        self,
        role: str,
        task: Task,
        workspace: Path,
        context: dict,
        instructions: str,
        contract: type[BaseModel],
        log_dir: Path,
        check_control: Callable[[], None],
        emit: Callable[[str, dict], None],
        timeout: float,
    ) -> dict:
        with self._lock:
            self.calls[role] = self.calls.get(role, 0) + 1
            count = self.calls[role]
        check_control()
        log_dir.mkdir(parents=True, exist_ok=True)
        emit(
            "worker.instantiated",
            {"role": role, "model": "scripted-fixture", "scenario": self.scenario},
        )
        if self.scenario == "security-fails-once" and role == "security" and count == 1:
            raise HXError("injected security reviewer timeout")
        if self.scenario == "startup-failure":
            raise StartupError("injected startup failure")
        if self.scenario == "malformed" and role == "correctness":
            result = {"chat": "looks good to me"}
        elif role == "implementer":
            from hx.demo import apply_fixture_fix

            apply_fixture_fix(workspace, task.acceptance)
            if self.scenario == "scope-violation":
                (workspace / "README.md").write_text("unauthorized edit", "utf-8")
            if self.scenario == "dirty-retry" and count == 1:
                (workspace / "backend" / "partial.py").write_text("PARTIAL = True\n", "utf-8")
                raise HXError("injected crash after partial edit")
            if self.scenario == "broken-revision" and count == 2:
                (workspace / "backend" / "app.py").write_text("def broken(\n", "utf-8")
            elif count > 1:
                path = workspace / "backend" / "app.py"
                path.write_text(
                    path.read_text("utf-8") + f"\n# Fixture revision {count}\n", "utf-8"
                )
            result = {
                "summary": "Fixture fix. Claimed commit: invented-123 (not evidence).",
                "tests_added": ["tests/test_regression.py"],
                "verification_commands": [],
                "limitations": [],
            }
        elif role == "consolidator":
            findings = context["source_findings"]
            result = {
                "candidate_commit": context["candidate_commit"],
                "groups": [
                    {"sources": [source], "summary": finding["claim"]}
                    for source, finding in findings.items()
                ],
                "summary": "Fixture consolidation",
            }
            if self.scenario == "drop-blocker":
                result["groups"] = []
        else:
            findings = []
            if self.scenario in {"always-blocking", "drop-blocker", "broken-revision"}:
                findings = [
                    {
                        "id": "f1",
                        "severity": "high",
                        "blocking": True,
                        "file": "backend/app.py",
                        "line": 1,
                        "claim": "Injected unresolved concern",
                        "evidence": "fixture evidence",
                    }
                ]
            result = {
                "candidate_commit": context["candidate_commit"],
                "could_not_inspect": [],
                "findings": findings,
            }
            if self.scenario == "stale-review":
                result["candidate_commit"] = "0" * 40
            if self.scenario == "review-write":
                (workspace / "backend" / "app.py").write_text(
                    "# forbidden reviewer edit\n", "utf-8"
                )
        atomic_write(log_dir / "result.json", canonical(result))
        return result
