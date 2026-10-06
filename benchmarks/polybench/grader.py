"""Use pinned upstream Docker utilities, parsers and scoring without changing tests."""
from __future__ import annotations

import ast
import importlib
from dataclasses import asdict
from pathlib import Path

from benchmarks.polybench.dependencies import prepare_dependencies
from benchmarks.polybench.prepare import write


def grade(row, patch: str, directory: Path, client):
    from poly_bench_evaluation import parsers
    from poly_bench_evaluation.constants import DEFAULT_TIMEOUT, REPO_TO_PARSER_CLASS
    from poly_bench_evaluation.docker_utils import DockerManager
    from poly_bench_evaluation.scoring import instance_level_scoring

    directory.mkdir(parents=True, exist_ok=False)
    manager = DockerManager("polybench_" + row["language"].lower() + "_" + row["instance_id"].lower(),
                            False, client)
    applied = False
    parsed = {}
    error = None
    patch_error = None
    stage = "container_setup"
    try:
        manager.create_container()
        stage = "dependency_setup"
        prepare_dependencies(manager.container, row.get("repo"), directory / "dependencies", row.get("base_commit"))
        # A fresh grader receives the hidden test patch; workers never receive it.
        manager.container.reload()
        for network in list(manager.container.attrs["NetworkSettings"]["Networks"]):
            client.networks.get(network).disconnect(manager.container)
        stage = "test_patch"
        manager.apply_patch_to_container(row["test_patch"], "test")
        if patch.strip():
            stage = "candidate_patch"
            applied = manager.apply_patch_to_container(patch, "code") == 0
        else:
            applied = True
        if applied:
            stage = "test_execution"
            manager.docker_run(row["test_command"], DEFAULT_TIMEOUT)
            logs = "\n".join(manager.run_logs)
            (directory / "test-output.txt").write_text(logs, "utf-8")
            parser = getattr(parsers, REPO_TO_PARSER_CLASS[row["repo"]])
            parsed = parser(test_content=logs).parse()
    except Exception as exc:
        if stage == "candidate_patch" and isinstance(exc, ValueError) and str(exc) == "Failed to apply patch.":
            patch_error = str(exc)
        else:
            error = f"{type(exc).__name__}: {exc}"
    finally:
        manager._cleanup()
    score = asdict(instance_level_scoring(row["instance_id"], parsed,
        ast.literal_eval(row["F2P"]), ast.literal_eval(row["P2P"]), applied, bool(patch.strip())))
    # Upstream scoring checks absence of P2P failures, not presence of every P2P.
    # Retain that definition; report observed coverage separately, never silently fix it.
    expected = set(ast.literal_eval(row["P2P"])) | set(ast.literal_eval(row["F2P"]))
    observed = set(score["passed_tests"]) | set(score["failed_tests"])
    score["expected_tests_unobserved"] = sorted(expected - observed)
    score["infrastructure_error"] = error
    score["candidate_patch_error"] = patch_error
    score["failure_stage"] = stage if error or patch_error else None
    write(directory / "score.json", score)
    return score


def register_vendor(path: Path):
    import sys
    sys.path.insert(0, str(path / "src"))
    importlib.import_module("poly_bench_evaluation.docker_utils")
