from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Settings(Contract):
    workflow: Literal["reviewed", "single"] = "reviewed"
    repository_matches: int = Field(default=6, ge=3, le=8)
    repair_feedback_chars: int = Field(default=2000, ge=800, le=2500)
    repair_token_reserve: int = Field(default=40000, ge=5000, le=200000)
    adapter: Literal["codex", "fake"] = "codex"
    worker_model: str = "gpt-6-luna"
    judgment_model: str = "gpt-6.1-sol"
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    windows_sandbox: Literal["elevated", "unelevated", "mxc"] = "elevated"
    max_revisions: int = Field(default=2, ge=0, le=5)
    max_attempts: int = Field(default=2, ge=1, le=5)
    max_resumes: int = Field(default=3, ge=0, le=10)
    attempt_timeout_seconds: int = Field(default=600, ge=1, le=3600)
    verification_timeout_seconds: int = Field(default=90, ge=1, le=600)
    run_timeout_seconds: int = Field(default=3600, ge=1, le=14400)
    max_observed_tokens: int = Field(default=400000, ge=1)
    max_log_bytes: int = Field(default=20000000, ge=1024)


def safe_relative(value: str) -> str:
    # Git paths always use forward slashes, including on Windows.
    if not value or "\\" in value or ":" in value or value.startswith("/"):
        raise ValueError("expected a relative POSIX path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("path cannot contain empty, dot or parent components")
    return value


class Task(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    repo: str
    report: str = Field(min_length=10, max_length=12000)
    kind: Literal["bug", "feature"] = "bug"
    base_commit: str = "HEAD"
    allowed_paths: list[str] = Field(default_factory=lambda: ["backend/**", "tests/**"])
    protected_paths: list[str] = Field(default_factory=lambda: ["tests/test_existing.py"])
    test_paths: list[str] = Field(default_factory=lambda: ["tests"])
    app_module: str = "backend.app:app"
    frontend: bool = False
    acceptance: (
        Literal["missing-task", "delete-task", "empty-title", "filter-completed", "rename-task"]
        | None
    ) = None

    @field_validator("base_commit")
    @classmethod
    def valid_ref(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", value) or value.startswith("-"):
            raise ValueError("invalid Git revision")
        return value

    @field_validator("allowed_paths", "protected_paths", "test_paths")
    @classmethod
    def valid_paths(cls, values: list[str]) -> list[str]:
        for value in values:
            safe_relative(value)
        if not values:
            raise ValueError("path list must not be empty")
        return values

    @field_validator("app_module")
    @classmethod
    def valid_module(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", value):
            raise ValueError("use an import path such as backend.app:app")
        return value

    def resolved(self, relative_to: Path) -> Task:
        path = Path(self.repo)
        return self.model_copy(update={"repo": str((relative_to / path).resolve())})


class WorkerSummary(Contract):
    summary: str
    tests_added: list[str]
    limitations: list[str]
    verification_commands: list[list[str]] = Field(max_length=3)

    @field_validator("verification_commands")
    @classmethod
    def bounded_commands(cls, commands: list[list[str]]) -> list[list[str]]:
        for command in commands:
            if not command or len(command) > 40 or any(
                not argument or len(argument) > 1000 or "\x00" in argument
                for argument in command
            ):
                raise ValueError("verification commands must be bounded nonempty argv lists")
        return commands


class Finding(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    severity: Literal["low", "medium", "high", "critical"]
    blocking: bool
    file: str
    line: int = Field(ge=1)
    claim: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator("file")
    @classmethod
    def valid_file(cls, value: str) -> str:
        return safe_relative(value)


class Review(Contract):
    candidate_commit: str
    could_not_inspect: list[str]
    findings: list[Finding]


class FindingGroup(Contract):
    sources: list[str] = Field(min_length=1)
    summary: str


class Consolidated(Contract):
    candidate_commit: str
    groups: list[FindingGroup]
    summary: str


class Candidate(Contract):
    base_commit: str
    input_commit: str
    candidate_commit: str
    changed_files: list[str]
    workspace: str
    diff_sha256: str
    verification_commands: list[list[str]] = Field(default_factory=list)
    public_contract: dict | None = None


class Check(Contract):
    name: str
    passed: bool
    evidence: str


class Verification(Contract):
    candidate_commit: str
    passed: bool
    checks: list[Check]
    changed_line_coverage: float | None
    known_gaps: list[str]


class Handoff(Contract):
    run_id: str
    candidate_commit: str
    verified: bool
    reviewed: bool
    status: Literal["ready_for_approval", "needs_attention"]
    approval: Literal["pending"] = "pending"
    revisions_used: int
    blocking_findings: list[str]
    known_gaps: list[str]
    review_steps: list[str]


class HXError(Exception):
    """Expected workflow failure, persisted for inspection and resume."""


class Cancelled(HXError):
    pass


class ProcessTimeout(HXError):
    """A child command exceeded its own limit, distinct from the run budget."""


class StartupError(HXError):
    """Configuration/startup failures are not retried."""


class GateError(HXError):
    """Evidence or scope violation; preserve work but do not advance."""
