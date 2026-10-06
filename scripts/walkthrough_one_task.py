"""Model-free red/green replay of the saved LangChain 6765 candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from benchmarks.polybench.containers import create, populate
from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.preflight import check_storage
from benchmarks.polybench.prepare import write
from benchmarks.polybench.test_environment import docker_environment
from hx.git import assert_clean, clone, git
from hx.models import Candidate
from hx.process import clean_env, execute

CASE = "langchain-ai__langchain-6765"
CAMPAIGN = Path(".hx/harness-repair-evaluation-v1")
REGRESSION_FILE = "tests/unit_tests/agents/test_serialization.py"
COMMAND = ["/usr/local/bin/python", "-m", "pytest", "-q",
           REGRESSION_FILE + "::test_initialize_agent_accepts_string_agent_type"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(root):
    import docker

    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + 2400
    trial = CAMPAIGN / "experiments/heldout-results" / ("full-" + CASE + "-1")
    score = json.loads((trial / "score.json").read_text())
    artifacts = trial / "state/runs" / score["run_id"] / "artifacts"
    candidate = Candidate.model_validate_json((artifacts / "implement.json").read_text())
    case = json.loads((CAMPAIGN / "images.json").read_text())[CASE]
    if not score["official_resolved"] or score["acceptance"]["candidate_commit"] != candidate.candidate_commit:
        raise RuntimeError("Saved accepted candidate identity does not match")
    assert_clean(Path(candidate.workspace), candidate.candidate_commit)
    # Use the sealed index rather than walking archived source/node_modules.
    historical = json.loads(Path(".hx/delivery-diagnostics-v1/exposure.json").read_text())["original_score_sha256"]
    for group in ("heldout-results", "private-evaluation"):
        historical.update({str(p): sha(p) for p in (CAMPAIGN / "experiments" / group).glob("*/score.json")})
    if not all(sha(Path(p)) == h for p, h in historical.items()):
        raise RuntimeError("Historical score seal mismatch before walkthrough")
    source_hashes = {str(p): sha(p) for directory in ("src/hx", "benchmarks/polybench")
                     for p in Path(directory).glob("*.py")}
    write(root / "plan.json", {"case": CASE, "classification": "Public diagnostic replay, not a new benchmark attempt",
        "model_calls": 0, "command": COMMAND, "candidate_commit": candidate.candidate_commit,
        "base_commit": candidate.base_commit, "image_id": case["image_id"],
        "historical_scores": historical, "runtime_sources": source_hashes,
        "script_sha256": sha(Path(__file__)), "maximum_wall_seconds": 2400})

    def control():
        if time.monotonic() >= deadline:
            raise TimeoutError("Single-task walkthrough deadline exhausted")

    def phase(name, **extra):
        write(root / "phase.json", {"phase": name, "case": CASE,
            "updated": time.time(), **extra})
        print(json.dumps({"event": name, **extra}), flush=True)

    client = docker.from_env(timeout=1800)
    try:
        phase("image.inspect")
        try:
            image = client.images.get(case["image_id"])
        except docker.errors.ImageNotFound:
            check_storage(CAMPAIGN, client)
            # Restore only the pinned image. Do not trim other campaigns' caches.
            digest = next(d for d in case["image_digests"] if d.startswith("ghcr.io/"))
            phase("image.pull", reference=digest)
            last = 0
            for event in client.api.pull(digest, stream=True, decode=True):
                control()
                if event.get("error"):
                    raise RuntimeError(event["error"]) from None
                if time.monotonic() - last > 30:
                    phase("image.pull.progress", status=event.get("status"),
                          layer=event.get("id"), progress=event.get("progressDetail", {}))
                    last = time.monotonic()
            image = client.images.get(case["image_id"])
        if image.id != case["image_id"]:
            raise RuntimeError("Pinned dependency image identity changed")

        # Both isolated workspaces receive the exact same worker-authored public
        # regression. Only the second gets the saved production patch.
        native = Path(case["execution_root"]) / "infra-checks" / ("one-task-" + root.name)
        native.mkdir(parents=True, exist_ok=False)
        base = clone(Path(case["repo_path"]), native / "before", candidate.base_commit)
        test_bytes = subprocess.run(["git", "-C", candidate.workspace, "show",
            candidate.candidate_commit + ":" + REGRESSION_FILE], check=True,
            capture_output=True, timeout=30).stdout
        (base / REGRESSION_FILE).write_bytes(test_bytes)
        git(base, "add", "--", REGRESSION_FILE)
        git(base, "commit", "-m", "Diagnostic: saved public regression on original source")
        before_commit = git(base, "rev-parse", "HEAD")
        repaired = clone(base, native / "after", before_commit)
        patch, delivery = production_patch(candidate)
        patch_path = root / "production.patch"
        patch_path.write_bytes(patch.encode())
        subprocess.run(["git", "-C", str(repaired), "apply", "--check", str(patch_path)],
                       check=True, capture_output=True, timeout=30)
        subprocess.run(["git", "-C", str(repaired), "apply", str(patch_path)],
                       check=True, capture_output=True, timeout=30)
        git(repaired, "add", "--all")
        git(repaired, "commit", "-m", "Diagnostic: saved production repair")
        after_commit = git(repaired, "rev-parse", "HEAD")
        write(root / "delivery.json", delivery)
        write(root / "workspaces.json", {"before": str(base), "after": str(repaired),
            "before_commit": before_commit, "after_commit": after_commit,
            "public_regression_sha256": hashlib.sha256(test_bytes).hexdigest()})

        results = {}
        for label, workspace, head in (("before", base, before_commit), ("after", repaired, after_commit)):
            control()
            phase("replay.started", stage=label)
            container, workdir = create(client, case, offline=True)
            try:
                populate(container, workdir, workspace, case)
                def run(name, argv, workdir=workdir, container=container, label=label):
                    code, out, err = execute(["docker", "exec", "-u", "1000:1000",
                        *docker_environment(), "-w", workdir, container.id, *argv],
                        root, clean_env(), root / label / name, min(180, deadline - time.monotonic()),
                        control, max_bytes=2_000_000)
                    record = {"exit_code": code, "argv": argv, "stdout": out, "stderr": err}
                    write(root / label / (name + ".json"), record)
                    return record
                regression = run("regression", COMMAND)
                compatibility = run("compatibility", candidate.verification_commands[0]) if label == "after" else None
                results[label] = {"regression": regression, "compatibility": compatibility}
                assert_clean(workspace, head)
                phase("replay.finished", stage=label, exit_code=regression["exit_code"])
            finally:
                container.remove(force=True)

        before = results["before"]["regression"]
        after = results["after"]["regression"]
        clean_fail = (before["exit_code"] == 1 and "AttributeError" in before["stdout"]
                      and "'str' object has no attribute 'value'" in before["stdout"]
                      and "1 failed" in before["stdout"])
        clean_pass = (after["exit_code"] == 0 and "1 passed" in after["stdout"]
                      and results["after"]["compatibility"]["exit_code"] == 0
                      and "3 passed" in results["after"]["compatibility"]["stdout"])
        if not all(sha(Path(p)) == h for p, h in historical.items()):
            raise RuntimeError("Historical score changed during walkthrough")
        if not all(sha(Path(p)) == h for p, h in source_hashes.items()):
            raise RuntimeError("Harness source changed during walkthrough")
        result = {"case": CASE, "reproduced_original_bug": clean_fail,
            "saved_patch_fixes_same_public_regression": clean_pass,
            "official_result": "Previously sealed resolved=true; official grader not rerun",
            "original_score_sha256": sha(trial / "score.json"),
            "historical_scores_unchanged": len(historical), "runtime_sources_unchanged": True,
            "model_calls": 0, "additional_reported_tokens": 0,
            "wall_seconds": time.monotonic() - started,
            "classification": "Public diagnostic, not an additional benchmark success"}
        write(root / "result.json", result)
        phase("complete", **result)
        if not clean_fail or not clean_pass:
            raise RuntimeError("Public red/green proof failed; inspect retained logs")
    except Exception as exc:
        write(root / "failure.json", {"error": str(exc), "elapsed_seconds": time.monotonic() - started})
        raise
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="New evidence directory; existing roots are rejected")
    main(parser.parse_args().root)
