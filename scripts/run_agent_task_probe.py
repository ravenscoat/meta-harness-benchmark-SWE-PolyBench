"""One explicitly budgeted development probe, never a harness promotion.

Generate one reusable scaffold from public failed-task evidence, validate its
executable integration, then solve the fixed task with unchanged official grade.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.storage_lifecycle import release_images
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.code_search import copy_experience, seal, sha
from hx.config import canonical
from hx.models import HXError
from hx.store import atomic_write
from hx.worker_scaffold import validate_scaffold
from scripts.agent_search_polybench import PolyBenchBackend
from scripts.overnight_limits import account_usage, can_start
from scripts.run_lean_three import prior_evidence
from scripts.worker_scaffold_search import exercise_scaffold

KEY = "mui__material-ui-19511"
SOURCE = Path(".hx/coding-seventeen-v1/tasks") / KEY
ALLOWANCE = 1_200_000


def write(path, value):
    atomic_write(path, canonical(value))


def run(root):
    root = root.resolve()
    with FileLock(".hx/single-evaluation-controller.lock", timeout=0):
        if root.exists():
            raise HXError("New task-probe root required; never restart")
        root.mkdir(parents=True)
        started = time.time()
        write(root / "controller.json", {"pid": os.getpid(), "started": started})
        private = Path("/opt/hx-polybench-runtime/v1") / root.name
        prepared = root / "prepared"
        prepared.mkdir()
        for name in ("dataset.csv", "selection.json", "images.json", "storage.json"):
            shutil.copyfile(SOURCE / name, prepared / name)
        shutil.copyfile(Path(".hx/solution-repairs-v1/tasks") / KEY / "settings.toml",
                        prepared / "settings.toml")
        shutil.copytree(SOURCE / "public", prepared / "public")
        shutil.copytree(SOURCE / "preflight", prepared / "preflight")
        case = json.loads((prepared / "images.json").read_text())[KEY]
        case["execution_root"] = str(private)
        write(prepared / "images.json", {KEY: case})
        storage = json.loads((prepared / "storage.json").read_text())
        storage["execution_root"] = str(private)
        write(prepared / "storage.json", storage)
        write(root / "backend-config.json", {"prepared_root": str(prepared), "private_root": str(private),
              "carrier_case": KEY, "proposal_seconds": 180,
              "case_provenance": {KEY: {"reference_informed": False, "previous_coding_exposure": True}}})
        _, _, historical = prior_evidence()
        lock_paths = [*Path("src/hx").glob("*.py"), *Path("src/hx/prompts").glob("*.md"),
                      *Path("src/hx/scaffolds").glob("*.py"), *Path("benchmarks/polybench").glob("*.py"),
                      *(runner.VENDOR / "src").rglob("*.py"), runner.BINARY,
                      Path(__file__), Path("scripts/overnight_limits.py"),
                      Path("scripts/run_agent_search.py"), Path("scripts/agent_search_polybench.py"),
                      Path("scripts/worker_scaffold_search.py"), root / "backend-config.json",
                      *[p for p in prepared.rglob("*") if p.is_file()]]
        plan = {"task": KEY, "task_number": 5, "classification": "Consumed-development single experimental scaffold probe",
                "development": [KEY], "heldout": [], "proposals": 1, "coding_trials": 1,
                "max_revisions": 1, "max_reported_tokens": ALLOWANCE,
                "started": started, "deadline": started + 10800,
                "model": "gpt-6.1-sol", "reasoning_effort": "medium", "trial_token_headroom": 750000,
                "source_locks": {str(p.resolve()): sha(p.read_bytes()) for p in lock_paths},
                "historical_scores": historical, "prior_repair_allowance_unchanged": True,
                "authorization": "User said do whats best after offered new 1.2M allowance; chosen recommended scope.",
                "limitation": "Not a paired search or promoted agent. In-flight token overshoot possible. No next task."}
        write(root / "plan.json", plan)
        write(root / "plan.lock.json", {"sha256": sha((root / "plan.json").read_bytes())})
        tokens, phase, trial = 0, "preparation", None
        public_hashes = {}
        engine_plan = SimpleNamespace(**plan)

        def control(headroom=0):
            if time.time() >= plan["deadline"] or tokens + headroom > ALLOWANCE:
                raise HXError("New one-task allowance/deadline exhausted")
            for name, expected in {**plan["source_locks"], **historical}.items():
                if sha(Path(name).read_bytes()) != expected:
                    raise HXError("Frozen source/history changed: " + name)
            if sha((root / "plan.json").read_bytes()) != sha(canonical(plan)):
                raise HXError("Frozen plan changed")
            if public_hashes and seal(root / "development") != public_hashes:
                raise HXError("Public proposer archive changed")

        def admission(headroom=0):
            control(headroom)
            quota = account_usage(runner.BINARY, runner.AUTH)
            write(root / "quota.json", quota)
            if not can_start(quota):
                raise HXError("Ordinary quota blocked; no automatic retry or credit redemption")
            if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
                raise HXError("40 GiB storage guard blocked")

        try:
            admission(950000)
            write(root / "phase.json", {"phase": "pinned_image_worker_preflight", "task": KEY})
            _, images, client, settings = runner.resources(prepared)
            try:
                ensure_image(client, prepared, case)
                receipt = worker_environment_check(client, images[KEY], Path(case["repo_path"]),
                           root / "worker-preflight" / KEY, settings, control, lambda *args: None)
                write(root / "worker-preflight.json", receipt)
            finally:
                client.close()
            baseline = Path("src/hx/scaffolds/single_call.py")
            old_trial = next(SOURCE.glob("experiments/heldout-results/*"))
            old_score = json.loads((old_trial / "score.json").read_text())
            candidate = json.loads((Path(".hx/solution-repairs-v1/tasks") / KEY / "seed-candidate.json").read_text())
            patch = subprocess.check_output(["git", "-C", candidate["workspace"], "diff",
                candidate["base_commit"], candidate["candidate_commit"], "--",
                "packages/material-ui-lab/src/useAutocomplete/useAutocomplete.js"], timeout=30)
            atomic_write(root / "saved-public-production.patch", patch)
            sources = {"baseline.py": baseline, "original-public-issue.json": SOURCE / "public" / (KEY + ".json"),
                       "prior-public-production.patch": root / "saved-public-production.patch"}
            for step in (old_trial / "state/runs" / old_score["run_id"] / "steps").glob("implement/attempt-1"):
                for name in ("prompt.txt", "stdout.txt", "stderr.txt"):
                    if (step / name).is_file():
                        sources["prior-worker/" + name] = step / name
            copy_experience(root / "development", sources)
            write(root / "development/prior-outcome.json", {"official_resolved": False,
                  "public_verified": True, "grader_error": None,
                  "limitation": "Aggregate failure does not reveal failed private assertion. Public patch only."})
            public_hashes = seal(root / "development")
            backend = PolyBenchBackend(root / "backend-config.json")
            phase = "proposal"
            admission(950000)
            write(root / "phase.json", {"phase": phase, "task": KEY})
            directory = root / "proposal"
            directory.mkdir()
            write(directory / "started.json", {"time": time.time()})
            proposal = backend.propose(root / "development", directory, engine_plan, control)
            tokens += proposal.reported_tokens
            write(directory / "proposal.json", proposal.model_dump())
            write(root / "usage.json", {"reported_tokens": tokens, "usage_known": proposal.usage_known})
            if not proposal.usage_known:
                raise HXError("Unknown proposer usage")
            scaffold = root / "candidate-scaffold.py"
            atomic_write(scaffold, proposal.source.encode())
            validate_scaffold(scaffold.read_bytes())
            if scaffold.read_bytes() == baseline.read_bytes():
                raise HXError("No reusable scaffold change; no identical fallback")
            control(750000)
            phase = "scaffold_integration"
            write(root / "phase.json", {"phase": phase, "task": KEY})
            if not exercise_scaffold(scaffold, private / "fixture-validation"):
                raise HXError("Scaffold real scripted-worker integration failed")
            write(root / "candidate-lock.json", {"sha256": sha(scaffold.read_bytes()),
                  "fixture_passed": True, "performance_promoted": False})
            admission(750000)
            phase = "coding_and_official_grade"
            write(root / "phase.json", {"phase": phase, "task": KEY})
            directory = root / "task-result"
            directory.mkdir()
            write(directory / "started.json", {"time": time.time(), "task": KEY})
            trial = backend.evaluate(scaffold, KEY, 1, directory, engine_plan, control)
            tokens += trial.reported_tokens
            write(root / "score.json", trial.model_dump())
            write(root / "usage.json", {"reported_tokens": tokens, "usage_known": trial.usage_known})
            control()
            if not trial.usage_known or trial.infrastructure_error or trial.missing_observations:
                raise HXError("Operational or unknown-usage outcome; preserve and stop")
            write(root / "final-audit.json", {"complete": True, "official_resolved": trial.official_resolved,
                  "trial": trial.model_dump(), "reported_tokens": tokens, "historical_scores_verified": len(historical),
                  "source_verified": True, "scaffold_sha256": sha(scaffold.read_bytes()),
                  "proposal_tokens": proposal.reported_tokens, "reference_informed": False,
                  "harness_performance_promoted": False, "root_elapsed_seconds": time.time() - started,
                  "limitation": plan["limitation"]})
            print(json.dumps({"event": "task_probe_completed", "official_resolved": trial.official_resolved,
                              "reported_tokens": tokens}), flush=True)
        except BaseException as error:
            write(root / "failure.json", {"phase": phase, "error": str(error), "reported_tokens": tokens,
                  "trial": trial.model_dump() if trial else None,
                  "retry_allowed": False, "unreturned_usage_may_be_unknown": True})
            raise
        finally:
            # Release only the recorded image after all model/grade work stops.
            if trial is not None:
                try:
                    _, _, client, _ = runner.resources(prepared)
                    try:
                        write(root / "image-release.json", release_images(client, [case]))
                    finally:
                        client.close()
                except Exception as error:
                    write(root / "cleanup-failure.json", {"error": str(error)})
            write(root / "controller.exited.json", {"pid": os.getpid(), "time": time.time()})
            write(root / "archive-lock.json", {"files": seal(root)})


if __name__ == "__main__":
    run(Path(sys.argv[1]))
