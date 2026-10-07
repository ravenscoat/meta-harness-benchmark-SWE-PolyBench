import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.polybench.engine import task_for
from benchmarks.polybench.grader import grade
from benchmarks.polybench.preflight import check_storage, reference_valid
from benchmarks.polybench.prepare import REPOSITORIES, prepare, select


def fixture_rows():
    rows = []
    for repos in REPOSITORIES.values():
        for repo, count in repos.items():
            for index in range(count + 1):
                rows.append({"repo": repo, "instance_id": repo.replace("/", "__") + f"-{index}",
                    "language": "Python", "task_category": "Bug Fix", "base_commit": "a" * 40,
                    "problem_statement": "Fix the documented public behavior.",
                    "patch": "EVALUATOR_ONLY_SENTINEL", "test_patch": "EVALUATOR_ONLY_SENTINEL",
                    "hints_text": "EVALUATOR_ONLY_SENTINEL", "F2P": "EVALUATOR_ONLY_SENTINEL"})
    return rows


def test_selection_does_not_depend_on_solution_or_test_contents():
    rows = fixture_rows()
    before = select(rows)
    for row in rows:
        row.update(patch="completely different solution", test_patch="new private tests",
                   hints_text="new hints", F2P="different grading expectations")
    assert select(list(reversed(rows))) == before
    repos = {split: {c["repo"] for c in before if c["split"] == split} for split in REPOSITORIES}
    assert not repos["setup"] & repos["development"]
    assert not repos["setup"] & repos["evaluation"]
    assert not repos["development"] & repos["evaluation"]


def test_public_export_does_not_include_grader_or_hint_fields(tmp_path):
    rows = fixture_rows()
    with (tmp_path / "dataset.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    prepare(tmp_path)
    exported = list((tmp_path / "public").glob("*.json"))
    assert len(exported) == 35
    for path in exported:
        text = path.read_text()
        assert "EVALUATOR_ONLY_SENTINEL" not in text
        assert set(json.loads(text)) == {"split", "id", "repo", "language", "category",
                                         "upstream_base", "problem_statement"}


def test_upstream_dotted_id_is_preserved_in_metadata_but_valid_for_hx(tmp_path):
    case = {"id": "mrdoob__three.js-14836", "repo_path": str(tmp_path),
            "sanitized_base": "a" * 40, "category": "Bug Fix"}
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / (case["id"] + ".json")).write_text(json.dumps({
        "problem_statement": "Fix the documented public behavior."}))
    task = task_for(tmp_path, case)
    assert task.id == "mrdoob__three-js-14836"
    assert case["id"] == "mrdoob__three.js-14836"


def test_storage_guard_uses_verified_wsl_backing_drive_and_stops_when_full(tmp_path, monkeypatch):
    docker_root = tmp_path / "linux-docker"
    physical_drive = tmp_path / "physical-D"
    docker_root.mkdir()
    physical_drive.mkdir()
    (tmp_path / "storage.json").write_text(json.dumps({
        "distribution": "Ubuntu", "docker_root": str(docker_root),
        "host_mount": str(physical_drive)}))
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    client = SimpleNamespace(info=lambda: {"DockerRootDir": str(docker_root)})
    observed = []

    def available(path):
        observed.append(path)
        return SimpleNamespace(free=150 * 1024**3)

    monkeypatch.setattr("benchmarks.polybench.preflight.shutil.disk_usage", available)
    check_storage(tmp_path, client)
    assert observed == [docker_root, physical_drive]
    monkeypatch.setattr("benchmarks.polybench.preflight.shutil.disk_usage",
                        lambda path: SimpleNamespace(free=(30 if path == physical_drive else 900) * 1024**3))
    with pytest.raises(RuntimeError, match="Insufficient Docker storage"):
        check_storage(tmp_path, client)
    monkeypatch.setenv("WSL_DISTRO_NAME", "OtherDistribution")
    with pytest.raises(RuntimeError, match="different WSL distribution"):
        check_storage(tmp_path, client)


@pytest.mark.parametrize("stage,message,rejected", [
    ("code", "Failed to apply patch.", True),
    ("test", "Failed to apply patch.", False),
    ("code", "Failed to create patch file in container", False),
])
def test_grading_distinguishes_candidate_rejection_from_broken_environment(tmp_path, monkeypatch, stage, message, rejected):
    @dataclass
    class Score:
        resolved: bool = False
        passed_tests: tuple = ()
        failed_tests: tuple = ()

    class Manager:
        def __init__(self, *args):
            self.container = SimpleNamespace(reload=lambda: None,
                attrs={"NetworkSettings": {"Networks": {}}})

        def create_container(self):
            pass

        def apply_patch_to_container(self, patch, kind):
            if kind == stage:
                raise ValueError(message)
            return 0

        def _cleanup(self):
            pass

    monkeypatch.setitem(sys.modules, "poly_bench_evaluation", SimpleNamespace(parsers=SimpleNamespace()))
    monkeypatch.setitem(sys.modules, "poly_bench_evaluation.constants",
                        SimpleNamespace(DEFAULT_TIMEOUT=1200, REPO_TO_PARSER_CLASS={}))
    monkeypatch.setitem(sys.modules, "poly_bench_evaluation.docker_utils", SimpleNamespace(DockerManager=Manager))
    monkeypatch.setitem(sys.modules, "poly_bench_evaluation.scoring",
                        SimpleNamespace(instance_level_scoring=lambda *args: Score()))
    row = {"language": "Python", "instance_id": "example__project-1",
           "test_patch": "private evaluator patch", "F2P": "[]", "P2P": "[]"}
    result = grade(row, "candidate patch", tmp_path / "grade", None)
    assert not result["resolved"]
    assert bool(result["candidate_patch_error"]) == rejected
    assert bool(result["infrastructure_error"]) != rejected


def test_native_attempt_workspaces_keep_isolated_git_history(project, tmp_path):
    from benchmarks.polybench.engine import PolyEngine
    from hx.git import git
    from hx.models import HXError

    task = next(iter(project.values()))
    engine = PolyEngine.__new__(PolyEngine)
    engine.case = {"execution_root": str(tmp_path / "native")}
    destination = tmp_path / "logs/attempt-1/workspace"
    base = git(Path(task.repo), "rev-parse", "HEAD")
    workspace = engine._clone(Path(task.repo), destination, base)
    assert workspace.is_relative_to(tmp_path / "native")
    assert not destination.exists()
    assert git(workspace, "rev-parse", "HEAD") == base
    assert not git(workspace, "remote")
    with pytest.raises(HXError, match="fresh directory"):
        engine._clone(Path(task.repo), destination, base)


def test_cache_releases_only_recorded_tags_without_containers(tmp_path):
    from benchmarks.polybench.image_cache import trim_images

    cases = {}
    images = {}
    for key in ("owned", "shared", "inuse", "keep"):
        reference = f"ghcr.io/example/{key}:v1.1"
        cases[key] = {"id": key, "language": "Python", "image_id": key,
                      "image_reference": reference, "image_digests": [f"ghcr.io/example/{key}@sha256:digest"]}
        tags = [f"polybench_python_{key}:latest", reference]
        if key == "shared":
            tags.append("user-project:latest")
        images[key] = SimpleNamespace(id=key, tags=tags,
            attrs={"RepoDigests": cases[key]["image_digests"]})
    (tmp_path / "images.json").write_text(json.dumps(cases))
    removed = []
    client = SimpleNamespace(images=SimpleNamespace(get=images.__getitem__,
        remove=lambda tag, force: removed.append((tag, force))),
        containers=SimpleNamespace(list=lambda all, filters: [object()] if filters["ancestor"] == "inuse" else []))
    trim_images(client, tmp_path, keep=["keep"])
    assert removed == [("ghcr.io/example/owned:v1.1", False),
                       ("ghcr.io/example/owned@sha256:digest", False),
                       ("polybench_python_owned:latest", False), ("owned", False)]


def test_reference_gate_follows_official_resolution_and_rejects_environment_errors():
    base = {"with_logs": True, "resolved": False, "infrastructure_error": None}
    gold = {"resolved": True, "infrastructure_error": None,
            "expected_tests_unobserved": ["declared regression test not observed"]}
    assert reference_valid(base, gold)
    assert not reference_valid(base, {**gold, "resolved": False})
    assert not reference_valid(base, {**gold, "infrastructure_error": "Broken test environment"})
    assert not reference_valid({**base, "resolved": True}, gold)
