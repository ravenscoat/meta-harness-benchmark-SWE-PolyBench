from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

from hx.models import Settings, Task

PROMPTS = Path(__file__).parent / "prompts"
ROLES = ("implementer", "correctness", "security", "consolidator")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_settings(path: Path | None) -> Settings:
    return Settings.model_validate(tomllib.loads(path.read_text("utf-8"))) if path else Settings()


def load_task(path: Path) -> Task:
    return Task.model_validate_json(path.read_text("utf-8")).resolved(path.parent)


def snapshot(settings: Settings) -> dict:
    prompts = {role: (PROMPTS / f"{role}.md").read_text("utf-8") for role in ROLES}
    # Runtime code, prompt text, model settings and CLI version all affect replay validity.
    runtime = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(__file__).parent.glob("*.py"))
    }
    cli_version = "fake-v1"
    if settings.adapter == "codex":
        executable = shutil.which("codex")
        if not executable:
            raise ValueError("Codex CLI is missing. Install it and run codex login first.")
        cli_version = subprocess.check_output(
            [executable, "--version"], text=True, timeout=10
        ).strip()
    value = {
        "settings": settings.model_dump(),
        "prompts": prompts,
        "runtime": runtime,
        "cli_version": cli_version,
        "blueprint": "issue-to-fix@1",
    }
    return {**value, "fingerprint": digest(value)}
