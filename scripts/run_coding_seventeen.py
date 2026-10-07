"""Seventeen locked environment-ready tasks, one retained image and shared budget."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.grader import grade, register_vendor
from benchmarks.polybench.image_cache import VERSION, ensure_image
from benchmarks.polybench.lean import LeanEngine
from benchmarks.polybench.preflight import reference_valid
from benchmarks.polybench.prepare import read_rows, sha, write
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.config import load_settings
from scripts.overnight_limits import account_usage, can_start
from scripts.run_lean_three import check_headroom, prior_evidence
from scripts.run_paper_benchmark import usage

SURVEY = Path(".hx/environment-twentyfive-v1")
PROPOSAL = Path(".hx/coding-seventeen-proposal-v1/proposal.json")


def locked_cases(proposal, results):
    ids = [r["case"] for r in results["rows"] if r["passed"]]
    cases = proposal["cases"]
    if len(ids) != 17 or [c["id"] for c in cases] != ids or len(set(ids)) != 17:
        raise RuntimeError("Exactly seventeen original passing identities required")
    if set(proposal["image_pins"]) != set(ids):
        raise RuntimeError("Exact original image pins required")
    return cases


def assert_unused(cases, history, descriptors):
    wanted = {c["id"] for c in cases}
    used = {json.loads(Path(p).read_text()).get("case") for p in history}
    if wanted & used or any(key in str(p) for p in descriptors for key in wanted):
        raise RuntimeError("A selected coding identity is already consumed")


def classify(row):
    if row["official_resolved"]:
        return "official_resolution"
    if row.get("grader_error"):
        return "grader_infrastructure_error"
    if row.get("candidate_patch_error"):
        return "patch_rejected"
    if not row["acceptance"].get("candidate_commit"):
        return "no_accepted_candidate"
    if row.get("unobserved_acceptance_tests"):
        return "required_tests_unobserved"
    return "observed_required_test_failure"


def report(root, plan):
    rows, tokens, pending = [], 0, []
    for child in sorted((root / "tasks").glob("*")):
        part, used, active = usage(child)
        rows.extend(part)
        tokens += used
        pending.extend(active)
    ids = [r["case"] for r in rows]
    if len(ids) != len(set(ids)) or not set(ids) <= set(plan["cases"]):
        raise RuntimeError("Unexpected or duplicate scores")
    for row in rows:
        row["classification"] = classify(row)
    result = {
        "planned_trials": 17,
        "scored_trials": len(rows),
        "complete": set(ids) == set(plan["cases"]),
        "rows": rows,
        "official_resolutions": sum(r["official_resolved"] for r in rows),
        "reported_tokens": tokens,
        "unscored_runs": pending,
        "workflow_seconds": sum(r["seconds"] for r in rows),
        "limitations": plan["limitations"],
    }
    write(root / "results.json", result)
    return result


def child_report(child):
    rows, tokens, pending = usage(child)
    value = {
        "planned_trials": 1,
        "scored_trials": len(rows),
        "complete": len(rows) == 1,
        "rows": rows,
        "reported_tokens": tokens,
        "unscored_runs": pending,
    }
    write(child / "experiments/report.json", value)
    return value


def validate(root, plan):
    if sha(root / "plan.json") != json.loads((root / "plan.lock.json").read_text())["sha256"]:
        raise RuntimeError("Plan changed")
    for name, expected in {**plan["sealed"], **plan["historical_scores"]}.items():
        if sha(Path(name)) != expected:
            raise RuntimeError("Frozen input/source/history changed: " + name)


def run(root):
    import docker

    with FileLock(".hx/single-evaluation-controller.lock", timeout=0):
        if root.exists():
            raise RuntimeError("New root required; never restart consumed roots")
        os.environ["PATH"] = str(runner.BINARY.parent) + os.pathsep + os.environ.get("PATH", "")
        proposal = json.loads(PROPOSAL.read_text())
        if (
            sha(PROPOSAL)
            != json.loads(PROPOSAL.with_name("proposal.lock.json").read_text())["sha256"]
        ):
            raise RuntimeError("Proposal changed")
        if (
            sha(SURVEY / "results.json") != proposal["parent_results_sha256"]
            or sha(SURVEY / "final-audit.json") != proposal["parent_final_audit_sha256"]
        ):
            raise RuntimeError("Survey evidence changed")
        cases = locked_cases(proposal, json.loads((SURVEY / "results.json").read_text()))
        _, _, history = prior_evidence()
        descriptors = [
            p
            for pattern in [
                "*/experiments/*/*/state/native-state.json",
                "*/tasks/*/experiments/*/*/state/native-state.json",
            ]
            for p in Path(".hx").glob(pattern)
        ]
        assert_unused(cases, history, descriptors)
        root.mkdir(parents=True)
        original = json.loads((SURVEY / "selection.json").read_text())
        for name in ["dataset.csv", "storage.json"]:
            shutil.copyfile(SURVEY / name, root / name)
        write(
            root / "selection.json",
            {
                **original,
                "cases": cases,
                "selection_rule": "Exactly17environment-passing tasks, original order, no replacement; readiness-selected diagnostic evaluation.",
            },
        )
        write(root / "images.json", proposal["image_pins"])
        settings = """adapter = "codex"
workflow = "single"
worker_model = "gpt-6.1-sol"
judgment_model = "gpt-6.1-sol"
reasoning_effort = "medium"
max_attempts = 1
max_revisions = 1
repair_token_reserve = 60000
max_observed_tokens = 300000
attempt_timeout_seconds = 600
verification_timeout_seconds = 180
run_timeout_seconds = 1200
max_log_bytes = 20000000
"""
        (root / "settings.toml").write_text(settings)
        data = {r["instance_id"]: r for r in read_rows(root / "dataset.csv")}
        if sha(root / "dataset.csv") != original["dataset_sha256"]:
            raise RuntimeError("Pinned dataset changed")
        for c in cases:
            source = SURVEY / "cases" / c["id"] / "source.json"
            pin = json.loads(source.read_text())
            if any(
                pin[k] != proposal["image_pins"][c["id"]][k]
                for k in ["image_id", "image_reference", "image_digests"]
            ):
                raise RuntimeError("Survey source image changed")
            repo = Path(pin["repo_path"])
            head = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
            ).strip()
            status = subprocess.check_output(
                ["git", "-C", str(repo), "status", "--porcelain"], text=True
            )
            if head != pin["sanitized_base"] or status:
                raise RuntimeError("Cached source changed")
            child = root / "tasks" / c["id"]
            child.mkdir(parents=True)
            for name in ["dataset.csv", "storage.json", "settings.toml"]:
                shutil.copyfile(root / name, child / name)
            write(child / "selection.json", {**original, "cases": [c]})
            # Native state/workspaces belong to the new run; sanitized source stays immutable.
            pin["execution_root"] = "/opt/hx-polybench-runtime/v1/" + root.name
            write(child / "images.json", {c["id"]: pin})
            write(child / "image-retention.json", {"version": VERSION, "cases": [c["id"]]})
            write(
                child / "public" / f"{c['id']}.json",
                {**c, "problem_statement": data[c["id"]]["problem_statement"]},
            )
            (child / "experiments").mkdir()
        started = time.time()
        files = [
            Path(__file__),
            PROPOSAL,
            PROPOSAL.with_name("proposal.lock.json"),
            SURVEY / "results.json",
            SURVEY / "final-audit.json",
            *Path("benchmarks/polybench").glob("*.py"),
            *Path("src/hx").glob("*.py"),
            *Path("src/hx/prompts").glob("*.md"),
            Path("scripts/run_lean_three.py"),
            Path("scripts/run_paper_benchmark.py"),
            Path("scripts/overnight_limits.py"),
        ]
        files += [p for p in root.rglob("*") if p.is_file()]
        files += [SURVEY / "cases" / c["id"] / "source.json" for c in cases]
        plan = {
            "cases": [c["id"] for c in cases],
            "started": started,
            "deadline": started + 28800,
            "max_reported_tokens": 8500000,
            "per_workflow_target": 300000,
            "repair_reserve": 60000,
            "parallelism": 1,
            "working_set_images": 1,
            "max_revisions": 1,
            "historical_scores": history,
            "sealed": {str(p.resolve()): sha(p) for p in files},
            "limitations": "17environment-readiness-selected tasks, one Sol6.1 medium solver each, no blind author. Not unbiased accuracy, paired/causal gain or leaderboard. Turn caps can overshoot; reported tokens are not dollars. Public checks and official outcomes separate; no tuning from official outcomes.",
        }
        write(root / "plan.json", plan)
        write(root / "plan.lock.json", {"sha256": sha(root / "plan.json")})
        write(
            root / "controller.json",
            {"pid": os.getpid(), "started": started, "deadline": plan["deadline"]},
        )
        shutil.copytree(
            "benchmarks/polybench",
            root / "runtime-source/benchmarks/polybench",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        runner.report = child_report
        client = docker.from_env(timeout=600)

        def admission(initial=False, wait=False):
            while True:
                result = report(root, plan)
                check_headroom(result["reported_tokens"], time.time(), plan, initial)
                validate(root, plan)
                quota = account_usage(runner.BINARY, runner.AUTH)
                write(root / "quota.json", quota)
                if can_start(quota):
                    return
                if not wait:
                    raise RuntimeError("Quota admission blocked before model work")
                write(
                    root / "phase.json", {"phase": "waiting_natural_quota", "updated": time.time()}
                )
                time.sleep(60)

        class GuardedLean(LeanEngine):
            def _worker(self, *args, **kwargs):
                admission()
                return super()._worker(*args, **kwargs)

        try:
            register_vendor(runner.VENDOR.resolve())
            for c in cases:
                key = c["id"]
                child = root / "tasks" / key
                admission(True, True)
                write(
                    root / "phase.json",
                    {"phase": "pinned_image", "case": key, "updated": time.time()},
                )
                pin = json.loads((child / "images.json").read_text())[key]
                ensure_image(client, child, pin)
                admission(True)
                write(
                    root / "phase.json",
                    {"phase": "worker_preflight", "case": key, "updated": time.time()},
                )
                worker_environment_check(
                    client,
                    pin,
                    Path(pin["repo_path"]),
                    child / "worker-preflight",
                    load_settings(child / "settings.toml"),
                    lambda: validate(root, plan),
                    lambda *args: None,
                )
                # Private reference checks stay entirely in grader containers, never worker context.
                write(
                    root / "phase.json",
                    {"phase": "official_reference_gate", "case": key, "updated": time.time()},
                )
                base = grade(data[key], "", child / "preflight" / key / "base", client)
                gold = grade(
                    data[key], data[key]["patch"], child / "preflight" / key / "reference", client
                )
                gate = {
                    "case": key,
                    "valid": reference_valid(base, gold),
                    "base_resolved": base["resolved"],
                    "reference_resolved": gold["resolved"],
                    "image_id": pin["image_id"],
                    "dataset_sha256": original["dataset_sha256"],
                    "gate_version": "official-resolution@2",
                }
                write(child / "preflight" / key / "validation.json", gate)
                if not gate["valid"]:
                    raise RuntimeError(
                        "Official reference setup gate failed; no task substitution or model call"
                    )
                runner.lock_sources(child)
                admission(True, True)
                write(root / "phase.json", {"phase": "coding", "case": key, "updated": time.time()})
                runner.run_case(
                    child,
                    key,
                    "lean",
                    start_guard=lambda: admission(True),
                    engine_factory=GuardedLean,
                )
                write(child / "controller.exited.json", {"time": time.time(), "case": key})
                result = report(root, plan)
                print(
                    json.dumps(
                        {
                            "event": "seventeen_scored",
                            "case": key,
                            "scored": result["scored_trials"],
                            "official_resolutions": result["official_resolutions"],
                        }
                    ),
                    flush=True,
                )
                if result["unscored_runs"] or any(
                    r.get("usage_known") is False or r.get("grader_error") for r in result["rows"]
                ):
                    raise RuntimeError("Operational or unknown-usage blocker retained")
                # Release the complete single-task image once its score and evidence exist.
                release_images(
                    client,
                    [pin],
                    emit=lambda r, child=child: write(child / "image-release.json", r),
                )
            validate(root, plan)
            write(
                root / "audit.json",
                {
                    "complete": report(root, plan)["complete"],
                    "historical_scores_verified": len(history),
                    "scores": {
                        str(p.relative_to(root)): sha(p)
                        for p in root.glob("tasks/*/experiments/heldout-results/*/score.json")
                    },
                },
            )
        except BaseException as error:
            write(
                root / "stop.json",
                {
                    "error": str(error),
                    "type": type(error).__name__,
                    "retry_allowed": False,
                    "time": time.time(),
                },
            )
            raise
        finally:
            client.close()
            report(root, plan)
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})


if __name__ == "__main__":
    import sys

    run(Path(sys.argv[1]))
