import pytest

from hx.git import check_baseline_links, git
from hx.models import GateError


@pytest.fixture
def linked_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'source.py').write_text('value = 1\n')
    git(repo, 'add', '--all')
    git(repo, 'commit', '-qm', 'source')
    oid = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'update-index', '--add', '--cacheinfo', '160000', oid, 'docs/example')
    git(repo, 'commit', '-qm', 'baseline gitlink')
    (repo / 'docs/example').mkdir(parents=True)
    return repo, git(repo, 'rev-parse', 'HEAD'), oid


def test_unchanged_uninitialized_gitlink_allows_regular_source_edits(linked_repo):
    repo, base, _ = linked_repo
    (repo / 'source.py').write_text('value = 2\n')
    git(repo, 'add', '--all')
    check_baseline_links(repo, base)
    (repo / 'docs/example').rmdir()
    check_baseline_links(repo, base)


@pytest.mark.parametrize('mutation', ['new', 'retarget', 'delete', 'replace', 'populate'])
def test_gitlink_mutations_are_rejected(linked_repo, mutation):
    repo, base, oid = linked_repo
    if mutation == 'new':
        git(repo, 'update-index', '--add', '--cacheinfo', '160000', oid, 'new')
    elif mutation == 'retarget':
        git(repo, 'update-index', '--cacheinfo', '160000', base, 'docs/example')
    elif mutation in {'delete', 'replace'}:
        git(repo, 'update-index', '--force-remove', 'docs/example')
        if mutation == 'replace':
            (repo / 'docs/example').rmdir()
            (repo / 'docs').mkdir(exist_ok=True)
            (repo / 'docs/example').write_text('replacement')
            git(repo, 'add', '--all')
    else:
        (repo / 'docs/example').mkdir(parents=True, exist_ok=True)
        (repo / 'docs/example/hidden.py').write_text('untracked content')
    with pytest.raises(GateError):
        check_baseline_links(repo, base)
