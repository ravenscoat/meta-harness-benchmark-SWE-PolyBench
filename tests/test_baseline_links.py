import os
from pathlib import Path

import pytest

from hx.git import check_scope, git
from hx.models import GateError, Task

pytestmark = pytest.mark.skipif(os.name == "nt", reason="real symlink checks run on the Linux benchmark runtime")


@pytest.fixture
def linked_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "source.py").write_text("value = 1\n")
    (repo / "link.py").symlink_to("source.py")
    git(repo, "add", "--all")
    git(repo, "commit", "-qm", "baseline")
    task = Task(id="link-test", repo=str(repo), base_commit=git(repo, "rev-parse", "HEAD"),
                report="Change regular source only", allowed_paths=["**"], protected_paths=["private/**"])
    return repo, task


def test_unchanged_internal_baseline_link_allows_regular_changes(linked_repo):
    repo, task = linked_repo
    (repo / "source.py").write_text("value = 2\n")
    git(repo, "add", "--all")
    check_scope(repo, ["source.py"], task)


@pytest.mark.parametrize("mutation", ["new", "retarget", "replace", "delete", "escape"])
def test_link_mutations_and_escapes_still_fail(linked_repo, mutation):
    repo, task = linked_repo
    link = repo / "link.py"
    if mutation != "new":
        link.unlink()
    if mutation == "new":
        (repo / "new.py").symlink_to("source.py")
    elif mutation == "retarget":
        link.symlink_to("other.py")
    elif mutation == "replace":
        link.write_text("ordinary replacement")
    elif mutation == "escape":
        link.symlink_to(Path("../../outside.py"))
    git(repo, "add", "--all")
    with pytest.raises(GateError):
        check_scope(repo, [], task)


@pytest.mark.parametrize("target", ["../../outside.py", "link.py"])
def test_unchanged_unsafe_baseline_links_are_rejected(linked_repo, target):
    repo, task = linked_repo
    (repo / "link.py").unlink()
    (repo / "link.py").symlink_to(target)
    git(repo, "add", "--all")
    git(repo, "commit", "-qm", "unsafe baseline")
    task = task.model_copy(update={"base_commit": git(repo, "rev-parse", "HEAD")})
    with pytest.raises(GateError, match="baseline symlink/path escape"):
        check_scope(repo, [], task)
