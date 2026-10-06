"""Separate public regression evidence from benchmark production-code delivery.

Classification uses public path conventions, never the evaluator test patch.
The full candidate remains immutable and independently verified.
"""
import hashlib
import re
import subprocess
from pathlib import PurePosixPath


def is_test_path(path):
    parts = PurePosixPath(path).parts
    if any(p in {"test", "tests", "__tests__", "__test__"} for p in parts[:-1]):
        return True
    name = parts[-1] if parts else ""
    return bool(re.search(r"(^test_.*\.py$|_test\.py$|\.(test|spec)\.[cm]?[jt]sx?$)", name))


def production_patch(candidate):
    def git(*args):
        return subprocess.run(["git", "-C", candidate.workspace, *args], check=True,
                              capture_output=True, timeout=60).stdout
    names = git("diff", "--name-only", "-z", "--no-renames",
                candidate.base_commit, candidate.candidate_commit).decode("utf-8").split("\0")
    names = [p for p in names if p]
    excluded = [p for p in names if is_test_path(p)]
    included = [p for p in names if not is_test_path(p)]
    full = git("diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
               candidate.base_commit, candidate.candidate_commit)
    patch = git("diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
                candidate.base_commit, candidate.candidate_commit, "--",
                *[":(literal)" + p for p in included]) if included else b""
    evidence = {"version": "public-test-path-projection@1",
        "candidate_commit": candidate.candidate_commit, "base_commit": candidate.base_commit,
        "included_paths": included, "excluded_public_test_paths": excluded,
        "full_candidate_patch_sha256": hashlib.sha256(full).hexdigest(),
        "delivered_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "rule": "Public test path conventions only; no private evaluator inputs.",
        "limitation": "Unconventional test paths may remain; production code under test directories is excluded."}
    return patch.decode("utf-8"), evidence
