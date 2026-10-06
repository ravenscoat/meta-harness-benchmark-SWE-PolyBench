from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

from hx.models import Candidate, GateError, HXError, Task
from hx.process import clean_env


def git(repo: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        "safe.directory=" + str(repo.resolve()),
        "-c",
        "core.hooksPath=" + os.devnull,
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "protocol.file.allow=always",
        "-C",
        str(repo),
        *args,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=clean_env({"GIT_TERMINAL_PROMPT": "0"}),
        timeout=30,
    )
    if result.returncode:
        raise HXError(result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def resolve_base(task: Task) -> str:
    repo = Path(task.repo)
    if not repo.is_dir():
        raise HXError(f"repository does not exist: {repo}")
    return git(repo, "rev-parse", "--verify", task.base_commit + "^{commit}")


def clone(source: Path, destination: Path, commit: str) -> Path:
    if destination.exists():
        raise HXError("attempt workspace already exists; a retry must use a fresh directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # --no-local prevents hard-linked object storage. Configuration is independent of the source.
    result = subprocess.run(
        [
            "git",
            "-c",
            "safe.directory=" + str(source.resolve()),
            "-c",
            "core.autocrlf=false",
            "clone",
            "--no-local",
            "--no-checkout",
            "--",
            str(source),
            str(destination),
        ],
        capture_output=True,
        text=True,
        env=clean_env({"GIT_TERMINAL_PROMPT": "0"}),
        timeout=30,
    )
    if result.returncode:
        raise HXError(result.stderr.strip())
    for remote in git(destination, "remote").splitlines():
        git(destination, "remote", "remove", remote)
    git(destination, "checkout", "--detach", commit)
    git(destination, "config", "user.name", "HX Runtime")
    git(destination, "config", "user.email", "hx@localhost")
    return destination


def assert_clean(repo: Path, commit: str) -> None:
    if not repo.exists() or git(repo, "rev-parse", "HEAD") != commit:
        raise GateError("saved workspace is missing or at a different revision")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise GateError("frozen candidate or review workspace was modified")
    if git(repo, "remote"):
        raise GateError("worker workspace gained a Git remote")


def check_baseline_links(repo: Path, base: str) -> None:
    baseline = {}
    gitlinks = {}
    for row in git(repo, "ls-tree", "-r", "-z", "--full-tree", base).split("\0"):
        if not row:
            continue
        metadata, name = row.split("\t", 1)
        mode, _, oid = metadata.split()
        if mode == "160000":
            gitlinks[name] = oid
        if mode == "120000":
            baseline[name] = oid
    current = {}
    current_gitlinks = {}
    for row in git(repo, "ls-files", "--stage", "-z").split("\0"):
        if not row:
            continue
        metadata, name = row.split("\t", 1)
        mode, oid, stage = metadata.split()
        if mode == "160000":
            if stage != "0" or gitlinks.get(name) != oid:
                raise GateError("new or modified submodules are forbidden: " + name)
            path = repo / name
            if (path.is_symlink() or not path.resolve().is_relative_to(repo.resolve())
                    or (path.exists() and (not path.is_dir() or any(path.iterdir())))):
                raise GateError("baseline submodules must remain uninitialized and empty: " + name)
            current_gitlinks[name] = oid
        if mode == "120000":
            if stage != "0" or baseline.get(name) != oid:
                raise GateError("new or modified symlinks are forbidden: " + name)
            path = repo / name
            try:
                safe = path.is_symlink() and path.resolve().is_relative_to(repo.resolve())
            except (OSError, RuntimeError):
                safe = False
            if not safe:
                raise GateError("baseline symlink/path escape is forbidden: " + name)
            current[name] = oid
    if current != baseline:
        raise GateError("baseline symlinks must remain unchanged")
    if current_gitlinks != gitlinks:
        raise GateError("baseline submodule entries must remain unchanged")


def check_scope(repo: Path, files: list[str], task: Task) -> None:
    for file in files:
        path = repo / file
        if not path.resolve().is_relative_to(repo.resolve()) or path.is_symlink():
            raise GateError(f"symlink/path escape is forbidden: {file}")
        if not any(fnmatch.fnmatchcase(file, pattern) for pattern in task.allowed_paths):
            raise GateError(f"change outside allowed paths: {file}")
        if any(fnmatch.fnmatchcase(file, pattern) for pattern in task.protected_paths):
            raise GateError(f"protected path changed: {file}")
    check_baseline_links(repo, task.base_commit)


def derive(repo: Path, base: str, input_commit: str, task: Task) -> Candidate:
    if git(repo, "rev-parse", "HEAD") != input_commit:
        raise GateError("worker altered Git history; only the runtime may create candidate commits")
    if git(repo, "remote"):
        raise GateError("worker configured a remote")
    git(repo, "add", "--all")
    attempt_files = git(repo, "diff", "--cached", "--name-only", input_commit).splitlines()
    if not attempt_files:
        raise HXError("worker made no changes")
    check_scope(repo, attempt_files, task)
    git(repo, "commit", "--quiet", "-m", f"HX candidate: {task.id}")
    commit = git(repo, "rev-parse", "HEAD")
    files = git(repo, "diff", "--name-only", base, commit).splitlines()
    check_scope(repo, files, task)
    diff = git(repo, "diff", "--no-ext-diff", "--no-textconv", base, commit)
    assert_clean(repo, commit)
    return Candidate(
        base_commit=base,
        input_commit=input_commit,
        candidate_commit=commit,
        changed_files=files,
        workspace=str(repo.resolve()),
        diff_sha256=hashlib.sha256(diff.encode()).hexdigest(),
    )


def validate_candidate(candidate: Candidate, task: Task) -> None:
    repo = Path(candidate.workspace)
    assert_clean(repo, candidate.candidate_commit)
    diff = git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        candidate.base_commit,
        candidate.candidate_commit,
    )
    if hashlib.sha256(diff.encode()).hexdigest() != candidate.diff_sha256:
        raise GateError("candidate diff integrity mismatch")
    files = git(
        repo, "diff", "--name-only", candidate.base_commit, candidate.candidate_commit
    ).splitlines()
    if files != candidate.changed_files:
        raise GateError("candidate changed-file evidence mismatch")
    check_scope(repo, files, task)
