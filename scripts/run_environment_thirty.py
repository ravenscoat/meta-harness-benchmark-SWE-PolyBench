"""Locked, model-free preparation survey; no coding or official scorer calls."""

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench.containers import create, extract_base, populate
from benchmarks.polybench.contract_coverage import structured_reports
from benchmarks.polybench.image_cache import VERSION, ensure_image, trim_images
from benchmarks.polybench.prepare import read_rows, sha, write
from benchmarks.polybench.report_capture import capture_argv
from benchmarks.polybench.test_environment import docker_environment
from benchmarks.polybench.worker_environment import build_check, worker_environment_check
from hx.check_execution import command_check
from hx.config import load_settings
from hx.process import clean_env
from scripts.run_lean_three import REPOS, SOURCE, prior_evidence

SEED = "environment-thirty-v1"
ANCHOR = Path(".hx/lean-evidence-three-v1")


def runner_report_passed(report):
    """Accept legacy Mocha outer whitespace, keeping exact name/count checks."""
    stats = report.get("stats", {})
    passes = report.get("passes", [])
    return (
        stats.get("tests") == 1
        and stats.get("passes") == 1
        and stats.get("failures") == 0
        and stats.get("pending", 0) == 0
        and not report.get("failures", [])
        and len(passes) == 1
        and isinstance(passes[0].get("fullTitle"), str)
        and passes[0]["fullTitle"].strip() == "HX environment runner smoke"
        and not passes[0].get("err", {})
    )


def select(rows, excluded, anchors):
    excluded = set(excluded) | {c["id"] for c in anchors}
    by_repo = {}
    for repo in REPOS:
        anchor = [c for c in anchors if c["repo"] == repo]
        if len(anchor) != 1:
            raise ValueError("One preselected anchor required per repository")
        eligible = [
            r
            for r in rows
            if r["repo"] == repo
            and r["instance_id"] not in excluded
            and r["task_category"] in {"Bug Fix", "Feature"}
            and 10 <= len(r["problem_statement"]) <= 11500
        ]
        eligible.sort(key=lambda r: hashlib.sha256((SEED + r["instance_id"]).encode()).hexdigest())
        if len(eligible) < 9:
            raise ValueError("Insufficient untouched metadata candidates: " + repo)
        by_repo[repo] = anchor + [
            {
                "id": r["instance_id"],
                "repo": repo,
                "split": "evaluation",
                "language": r["language"],
                "category": r["task_category"],
                "upstream_base": r["base_commit"],
            }
            for r in eligible[:9]
        ]
    return [by_repo[repo][n] for n in range(10) for repo in REPOS]


def registry_pin(case):
    import requests

    repo = "timesler/swe-polybench.eval.x86_64." + case["id"].lower()
    with requests.Session() as session:
        response = session.get(
            "https://ghcr.io/token",
            params={"service": "ghcr.io", "scope": "repository:" + repo + ":pull"},
            timeout=30,
        )
        response.raise_for_status()
        session.headers["Authorization"] = "Bearer " + response.json()["token"]
        session.headers["Accept"] = (
            "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
        )
        manifest = session.get("https://ghcr.io/v2/" + repo + "/manifests/v1.1", timeout=30)
        manifest.raise_for_status()
        digest = "sha256:" + hashlib.sha256(manifest.content).hexdigest()
        if manifest.headers.get("Docker-Content-Digest") != digest:
            raise RuntimeError("Registry manifest digest mismatch")
        data = manifest.json()
        if not isinstance(data.get("config"), dict) or not isinstance(data.get("layers"), list):
            raise RuntimeError("Single-platform manifest required; no mutable fallback")
        return {
            **case,
            "image_id": digest,
            "image_reference": "ghcr.io/" + repo + ":v1.1",
            "image_digests": ["ghcr.io/" + repo + "@" + digest],
        }, data


def runner_smoke(client, case, workspace, directory, settings, control):
    """Actually run the installed runner, explicitly separate from repository tests."""
    container, workdir = create(client, case, offline=True)
    try:
        populate(container, workdir, workspace, case)
        build = build_check(
            container,
            workdir,
            workspace,
            case,
            directory / "build",
            settings,
            control,
            lambda *a: None,
        )
        if build and not build.passed:
            raise RuntimeError("Public runner prerequisite build failed")
        # No repo mutation, fixtures, evaluator data or model credentials. The
        # native Mocha API is compatible with the pinned old/new runner versions.
        code = "const M=require('mocha'),m=new M({reporter:'json'});m.suite.addTest(new M.Test('HX environment runner smoke',function(){require('assert').strictEqual(2+2,4)}));m.run(n=>{process.exitCode=n?1:0});"
        argv = ["node", "-e", code, "--", "--reporter", "json"]
        logs = directory / "runner"
        check = command_check(
            "runner_execution",
            [
                "docker",
                "exec",
                "-u",
                "1000:1000",
                *docker_environment(),
                "-w",
                workdir,
                container.id,
                *capture_argv(argv, settings.max_log_bytes),
            ],
            directory,
            clean_env(),
            logs,
            settings,
            control,
            lambda *a: None,
        )
        text = (logs / "stdout.txt").read_text(errors="replace")
        reports = list(structured_reports(text))
        valid = check.passed and any(runner_report_passed(v) for v in reports)
        if not valid:
            raise RuntimeError(
                "Runner execution or complete named JSON capture failed: " + check.evidence
            )
        write(
            directory / "receipt.json",
            {
                "passed": True,
                "check": check.model_dump(),
                "stdout_sha256": sha(logs / "stdout.txt"),
                "stderr_sha256": sha(logs / "stderr.txt"),
                "limitation": "Synthetic installed-runner smoke, not repository behavioral tests or task correctness.",
            },
        )
        return True
    finally:
        container.remove(force=True)


def run(root, recheck_from=None):
    import docker

    with FileLock(".hx/single-evaluation-controller.lock", timeout=0):
        if root.exists():
            raise RuntimeError("New preparation root required; never overwrite attempts")
        excluded, exposure, history = prior_evidence()
        original = json.loads((SOURCE / "selection.json").read_text())
        if sha(SOURCE / "dataset.csv") != original["dataset_sha256"]:
            raise RuntimeError("Pinned dataset changed")
        parent_plan = None
        if recheck_from:
            parent_plan = json.loads((recheck_from / "plan.json").read_text())
            if not (recheck_from / "controller.exited.json").exists():
                raise RuntimeError("Recheck requires stopped parent controller")
            if (
                sha(recheck_from / "plan.json")
                != json.loads((recheck_from / "plan.lock.json").read_text())["sha256"]
            ):
                raise RuntimeError("Parent plan changed")
            cases = json.loads((recheck_from / "selection.json").read_text())["cases"]
            if [c["id"] for c in cases] != parent_plan["cases"]:
                raise RuntimeError("Recheck scope changed")
            for n, h in parent_plan["inputs"].items():
                if sha(Path(n)) != h:
                    raise RuntimeError("Parent preparation inputs changed")
        else:
            anchors = json.loads((ANCHOR / "selection.json").read_text())["cases"]
            cases = select(read_rows(SOURCE / "dataset.csv"), excluded, anchors)
        root.mkdir(parents=True)
        for name in ["dataset.csv", "storage.json"]:
            shutil.copyfile(SOURCE / name, root / name)
        shutil.copyfile(ANCHOR / "settings.toml", root / "settings.toml")
        write(
            root / "selection.json",
            {
                **original,
                "cases": cases,
                "seed": SEED,
                "selection_rule": "Three preselected uncoded anchors plus nine untouched metadata hash-ranked bugs/features per repository. All30 locked before image/build results; no replacement.",
            },
        )
        started = parent_plan["started"] if parent_plan else time.time()
        inputs = [
            root / n for n in ["dataset.csv", "storage.json", "settings.toml", "selection.json"]
        ]
        files = [
            Path(__file__),
            *Path("benchmarks/polybench").glob("*.py"),
            *Path("src/hx").glob("*.py"),
            Path("scripts/run_lean_three.py"),
        ]
        plan = {
            "version": "environment-thirty@1",
            "cases": [c["id"] for c in cases],
            "started": started,
            "deadline": parent_plan["deadline"] if parent_plan else started + 28800,
            "model_calls_allowed": 0,
            "official_calls_allowed": 0,
            "parallelism": 1,
            "working_set_images": 3,
            "inputs": {str(p.resolve()): sha(p) for p in inputs},
            "source": {str(p.resolve()): sha(p) for p in files},
            "historical_scores": history,
            "exposure_records": exposure,
            "limitations": "30selected JS/TS-family tasks,10each MUI/Svelte/Serverless;3anchors27new. No coding/scorer calls. Dependency/build and synthetic runner execution are not task correctness.",
            "recheck_from": str(recheck_from.resolve()) if recheck_from else None,
        }
        write(root / "plan.json", plan)
        write(root / "plan.lock.json", {"sha256": sha(root / "plan.json")})
        shutil.copytree(
            "benchmarks/polybench",
            root / "runtime-source/benchmarks/polybench",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        write(
            root / "controller.json",
            {"pid": os.getpid(), "started": started, "deadline": plan["deadline"]},
        )
        pins = {}
        rows = []
        client = None

        def control():
            if time.time() >= plan["deadline"]:
                raise RuntimeError("Preparation deadline exhausted")
            if (
                sha(root / "plan.json")
                != json.loads((root / "plan.lock.json").read_text())["sha256"]
            ):
                raise RuntimeError("Preparation plan changed")
            if (root / "images.lock.json").exists() and sha(root / "images.json") != json.loads(
                (root / "images.lock.json").read_text()
            )["sha256"]:
                raise RuntimeError("Registry image pins changed")
            for n, h in {**plan["inputs"], **plan["source"]}.items():
                if sha(Path(n)) != h:
                    raise RuntimeError("Frozen preparation input/source changed: " + n)

        def report():
            value = {
                "planned": 30,
                "attempted": len(rows),
                "complete": len(rows) == 30,
                "passed": sum(r["passed"] for r in rows),
                "rows": rows,
                "model_calls": 0,
                "official_calls": 0,
                "reported_model_tokens": 0,
            }
            write(root / "results.json", value)
            return value

        try:
            old_pins = {}
            if recheck_from and (recheck_from / "images.lock.json").exists():
                if (
                    sha(recheck_from / "images.json")
                    != json.loads((recheck_from / "images.lock.json").read_text())["sha256"]
                ):
                    raise RuntimeError("Parent image pins changed")
                old_pins = json.loads((recheck_from / "images.json").read_text())
            for case in cases:
                control()
                write(
                    root / "phase.json",
                    {"stage": "registry_pin", "case": case["id"], "updated": time.time()},
                )
                try:
                    if case["id"] in old_pins:
                        pin = old_pins[case["id"]]
                        manifest = {"retained_parent_pin": True}
                    else:
                        pin, manifest = registry_pin(case)
                    pins[case["id"]] = pin
                    write(
                        root / "registry" / (case["id"] + ".json"),
                        {"pin": pin, "manifest": manifest},
                    )
                except Exception as e:
                    write(
                        root / "registry" / (case["id"] + ".json"),
                        {"error": str(e), "type": type(e).__name__},
                    )
            write(root / "images.json", pins)
            write(root / "images.lock.json", {"sha256": sha(root / "images.json")})
            client = docker.from_env(timeout=120)
            settings = load_settings(root / "settings.toml")
            base_root = Path("/opt/hx-polybench-runtime/v1") / root.name / "bases"
            for offset in range(0, 30, 3):
                group = cases[offset : offset + 3]
                group_root = root / "groups" / str(offset // 3 + 1)
                write(group_root / "selection.json", {"cases": group})
                shutil.copyfile(root / "storage.json", group_root / "storage.json")
                group_pins = {c["id"]: pins[c["id"]] for c in group if c["id"] in pins}
                write(group_root / "images.json", group_pins)
                write(
                    group_root / "image-retention.json",
                    {"version": VERSION, "cases": [c["id"] for c in group]},
                )
                trim_images(client, root, keep=[p["image_id"] for p in group_pins.values()])
                for case in group:
                    control()
                    key = case["id"]
                    stage = "pinned_image"
                    write(
                        root / "phase.json", {"stage": stage, "case": key, "updated": time.time()}
                    )
                    try:
                        if key not in pins:
                            raise RuntimeError(
                                "Registry pin unavailable; see retained registry failure"
                            )
                        pin = dict(pins[key])
                        ensure_image(client, group_root, pin)
                        stage = "source_extraction"
                        workspace = base_root / key
                        pin["sanitized_base"] = extract_base(client, pin, workspace)
                        pin["repo_path"] = str(workspace)
                        pin["execution_root"] = str(base_root.parent)
                        directory = root / "cases" / key
                        write(directory / "source.json", pin)
                        stage = "worker_population_build"
                        write(
                            root / "phase.json",
                            {"stage": stage, "case": key, "updated": time.time()},
                        )
                        receipt = worker_environment_check(
                            client,
                            pin,
                            workspace,
                            directory / "worker",
                            settings,
                            control,
                            lambda *a: None,
                        )
                        stage = "runner_execution"
                        runner_smoke(
                            client, pin, workspace, directory / "public-runner", settings, control
                        )
                        rows.append(
                            {
                                "case": key,
                                "passed": True,
                                "worker": receipt,
                                "runner_executed": True,
                            }
                        )
                    except Exception as e:
                        rows.append(
                            {
                                "case": key,
                                "passed": False,
                                "stage": stage,
                                "error": str(e),
                                "type": type(e).__name__,
                            }
                        )
                    report()
                    print(
                        json.dumps(
                            {
                                "event": "environment_checked",
                                "case": key,
                                "passed": rows[-1]["passed"],
                                "attempted": len(rows),
                            }
                        ),
                        flush=True,
                    )
            control()
            for n, h in history.items():
                if sha(Path(n)) != h:
                    raise RuntimeError("Historical score changed: " + n)
            write(
                root / "audit.json",
                {
                    **report(),
                    "historical_score_files_verified": len(history),
                    "plan_source_inputs_verified": True,
                    "plan_sha256": sha(root / "plan.json"),
                    "image_pins_sha256": sha(root / "images.json"),
                    "limitations": plan["limitations"],
                },
            )
        except BaseException as e:
            write(
                root / "stop.json",
                {"error": str(e), "type": type(e).__name__, "retry_allowed": False},
            )
            raise
        finally:
            if client:
                client.close()
            report()
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--recheck-from", type=Path)
    args = parser.parse_args()
    run(args.root, args.recheck_from)
