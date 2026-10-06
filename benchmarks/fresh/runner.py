"""Validate and run a frozen, paired before/after experiment on new tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from benchmarks.fresh.collection import HERE, backend, build
from hx.challenge_eval import prepare_frontend
from hx.config import canonical, digest, load_settings, load_task, snapshot
from hx.engine import Engine
from hx.git import assert_clean, clone, derive
from hx.models import Candidate, HXError
from hx.optimization import final_candidate
from hx.process import clean_env, execute
from hx.store import Store, atomic_write, now


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_cache(root):
    # Each runtime resolves ASSETS relative to its own copied package root.
    source = Path(__file__).parents[2] / ".hx/npm-cache"
    for name in ("baseline", "improved"):
        shutil.copytree(source, root / f"runtime-{name}/.hx/npm-cache")


def dependency_preflight(root, case):
    task = load_task(Path(case["task"]))
    for name in ("baseline", "improved"):
        runtime = root / f"runtime-{name}"
        directory = root / "dependency-preflight" / name
        repo = clone(Path(task.repo), directory / "workspace", task.base_commit)
        program = "from pathlib import Path;from hx.challenge_eval import prepare_frontend;prepare_frontend(Path(" + repr(str(repo)) + "),Path(" + repr(str(directory / "npm")) + "))"
        code, _, err = execute([sys.executable, "-c", program], root,
            clean_env({"PYTHONPATH": str(runtime / "src")}), directory / "process", 120, lambda: None)
        if code:
            raise HXError("frozen runtime dependency preflight failed: " + name + " / " + err[-2000:])


def environment():
    bundle = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    value = {"node": str(bundle / "bin/node.exe"),
             "playwright": str(bundle / "node_modules/playwright"),
             "browser_executable": "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"}
    if not all(Path(value[key]).exists() for key in ("node", "playwright", "browser_executable")):
        raise HXError("bundled Node/Playwright unavailable")
    return value


def acceptance(candidate, case, root, settings, browser_env):
    repo = clone(Path(candidate.workspace), root / "workspace", candidate.candidate_commit)
    prepare_frontend(repo, root / "dependencies")
    groups = {}
    for name, argv, cwd in (
        ("backend", [sys.executable, str(HERE / "private_backend.py"), case["id"]], repo),
        ("browser", [browser_env["node"], str(HERE / "browser.cjs"), str(repo), case["id"],
                     sys.executable, browser_env["playwright"], str(root / "browser-artifacts"),
                     browser_env["browser_executable"]], repo),
    ):
        try:
            code, _, _ = execute(argv, cwd, clean_env({"PYTHONPATH": str(repo),
                "HX_DB": str(root / "private.sqlite3")}), root / name,
                settings.verification_timeout_seconds, lambda: None,
                max_bytes=settings.max_log_bytes)
            groups[name] = code == 0
        except HXError as exc:
            groups[name] = False
            atomic_write(root / name / "evaluation-error.txt", str(exc).encode())
    assert_clean(repo, candidate.candidate_commit)
    return {"passed": all(groups.values()), "groups": groups,
            "candidate_commit": candidate.candidate_commit}


def validate(manifest_path, root, settings):
    manifest = json.loads(manifest_path.read_text("utf-8"))
    env = environment()
    rows = []
    for case in manifest["cases"]:
        task = load_task(Path(case["task"]))
        reference_repo = clone(Path(task.repo), root / case["id"] / "reference-source", task.base_commit)
        (reference_repo / "backend/app.py").write_text(backend(case["id"], True), encoding="utf-8")
        (reference_repo / "frontend/src/editor.jsx").write_bytes((HERE / "editor_reference.jsx").read_bytes())
        reference = derive(reference_repo, task.base_commit, task.base_commit, task)
        seed = Candidate(base_commit=task.base_commit, input_commit=task.base_commit,
                         candidate_commit=task.base_commit, changed_files=[], workspace=task.repo,
                         diff_sha256=hashlib.sha256(b"").hexdigest())
        seed_grade = acceptance(seed, case, root / case["id"] / "seed", settings, env)
        ref_grade = acceptance(reference, case, root / case["id"] / "reference", settings, env)
        engine = Engine(Store(root / case["id"] / "visible-state"), settings)
        verification = engine.verifier.run(reference, task, root / case["id"] / "visible", lambda: None, lambda *_: None)
        row = {"case": case["id"], "seed": seed_grade, "reference": ref_grade,
               "visible_reference": verification.model_dump(),
               "valid": not any(seed_grade["groups"].values()) and ref_grade["passed"] and verification.passed}
        rows.append(row)
        atomic_write(root / "validation.json", canonical({"valid": all(r["valid"] for r in rows),
                     "complete": len(rows) == len(manifest["cases"]), "rows": rows,
                     "manifest_sha": sha(manifest_path),
                     "evaluators": {name: sha(HERE / name) for name in ("private_backend.py", "browser.cjs")}}))
        print(json.dumps({"event": "case.validated", "case": case["id"], "valid": row["valid"],
                          "seed": seed_grade["groups"], "reference": ref_grade["groups"]}), flush=True)
    return all(row["valid"] for row in rows)


class TrialEngine(Engine):
    def one_shot(self, run_id):
        run = self.store.get(run_id)
        task = load_task_body(run["task"])
        start = time.monotonic()
        deadline = start + self.settings.run_timeout_seconds
        self.store.update(run_id, status="running")
        try:
            candidate = self._implementation(run_id, "implement", task, None, {}, deadline)
            verification = self._verify(run_id, 0, candidate, task, deadline)
            self.store.update(run_id, status="baseline_complete", baseline_candidate=candidate.model_dump(),
                              baseline_verified=verification.passed)
        except Exception as exc:
            self.store.update(run_id, status="failed", error=str(exc))
        finally:
            self.store.update(run_id, elapsed_seconds=time.monotonic() - start)
            self.store.export_events(run_id)
        return self.store.get(run_id)


def load_task_body(value):
    from hx.models import Task

    return Task.model_validate(value)


def trial(root, index):
    plan = json.loads((root / "plan.json").read_text("utf-8"))
    item = plan["trials"][index]
    case, arm = item["case"], item["arm"]
    settings = load_settings(root / "campaign.toml")
    task = load_task(Path(case["task"]))
    if digest(task.model_dump()) != case["task_sha256"]:
        raise HXError("task changed after freezing")
    directory = root / "heldout-results" / item["key"]
    identity = digest({"item": item, "runtime": snapshot(settings)["fingerprint"],
                       "plan_sha": sha(root / "plan.json")})
    saved = directory / "score.json"
    if saved.exists():
        score = json.loads(saved.read_text("utf-8"))
        if score["identity"] != identity:
            raise HXError("trial identity changed")
        return score
    store = Store(directory / "state")
    engine = TrialEngine(store, settings)
    existing = store.list()
    if existing:
        run = existing[0]
        if run["status"] in {"pending", "running", "failed", "cancelled"}:
            if arm == "single":
                raise HXError("interrupted one-shot: retain evidence and start a new campaign")
            run = engine.execute(run["id"], resume=run["status"] != "pending")
    else:
        run = engine.create(task)
        run = engine.one_shot(run["id"]) if arm == "single" else engine.execute(run["id"])
    candidate = final_candidate(store, run)
    grade = {"passed": False, "groups": {}, "candidate_commit": None}
    if candidate:
        grading = root / "private-evaluation" / item["key"]
        if grading.exists():
            # Preserve interrupted grader work; never reuse its database.
            grading = grading.with_name(grading.name + "-" + str(time.time_ns()))
        grade = acceptance(candidate, case, grading, settings, plan["environment"])
    visible = run.get("baseline_verified", (run.get("handoff") or {}).get("verified", False))
    score = {"identity": identity, "arm": arm, "case": case["id"], "split": "heldout",
             "repeat": item["repeat"], "run_id": run["id"], "status": run["status"],
             "task_success": bool(grade["passed"] and visible and run["status"] in {
                 "baseline_complete", "ready_for_approval", "needs_attention"}),
             "acceptance": grade, "visible_verified": visible,
             "seconds": run["elapsed_seconds"], "observed_tokens": run["observed_tokens"],
             "error": run["error"], "fingerprint": engine.config["fingerprint"]}
    atomic_write(saved, canonical(score))
    return score


def prepare(root, manifest_path, validation_path, baseline, config, repeats):
    if root.exists() and any(root.iterdir()):
        raise HXError("new campaign directory must be empty")
    validation = json.loads(validation_path.read_text("utf-8"))
    if not validation.get("complete") or not validation.get("valid"):
        raise HXError("complete seeded/reference validation required")
    if not all(row.get("valid") for row in validation.get("rows", [])):
        raise HXError("validation contains an invalid reference/seed pair")
    if validation.get("manifest_sha") != sha(manifest_path):
        raise HXError("validation belongs to a different manifest")
    if validation.get("evaluators") != {name: sha(HERE / name) for name in ("private_backend.py", "browser.cjs")}:
        raise HXError("evaluator changed after validation")
    archive_hashes = json.loads((baseline / "source-sha256.json").read_text("utf-8"))
    for path, expected in archive_hashes.items():
        if path.startswith("src/hx/") and sha(baseline / path) != expected:
            raise HXError("archived baseline changed: " + path)
    root.mkdir(parents=True, exist_ok=True)
    copy_cache(root)
    shutil.copy2(config, root / "campaign.toml")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if {row["case"] for row in validation["rows"]} != {case["id"] for case in manifest["cases"]}:
        raise HXError("validation does not cover the exact task collection")
    trials = []
    arms = ["single", "full", "improved"]
    for repeat in range(1, repeats + 1):
        for number, case in enumerate(manifest["cases"]):
            order = arms[(number + repeat - 1) % 3:] + arms[:(number + repeat - 1) % 3]
            for arm in order:
                trials.append({"case": case, "arm": arm, "repeat": repeat,
                               "key": f"{arm}-{case['id']}-{repeat}"})
    shutil.copytree(baseline / "src/hx", root / "runtime-baseline/src/hx", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(Path(__file__).parents[2] / "src/hx", root / "runtime-improved/src/hx", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(HERE, root / "protocol/benchmarks/fresh", ignore=shutil.ignore_patterns("__pycache__"))
    dependency_preflight(root, manifest["cases"][0])
    shutil.copy2(validation_path, root / "validation.json")
    shutil.copy2(manifest_path, root / "manifest.json")
    plan = {"created_at": now(), "manifest_sha": sha(manifest_path),
            "validation_sha": sha(validation_path), "baseline": str(baseline.resolve()),
            "repeats": repeats, "environment": environment(), "trials": trials,
            "protocol": "Fixed comparison; all tasks prospectively reserved; no optimizer or retuning.",
            "limits": "Shared per-task ceilings; different realized compute; synthetic shared scaffolding; no independent human labels."}
    atomic_write(root / "plan.json", canonical(plan))
    hashes = {p.relative_to(root).as_posix(): sha(p) for folder in ("runtime-baseline/src", "runtime-improved/src", "protocol")
              for p in sorted((root / folder).rglob("*")) if p.is_file()}
    hashes.update({p: sha(root / p) for p in ("plan.json", "campaign.toml", "manifest.json", "validation.json")})
    atomic_write(root / "frozen-sha256.json", canonical(hashes))
    write_report(root, plan, [])


def write_report(root, plan, rows):
    totals = {}
    for arm in ("single", "full", "improved"):
        selected = [r for r in rows if r["arm"] == arm]
        totals["heldout/" + arm] = {"passed": sum(r["task_success"] for r in selected), "n": len(selected),
            "tokens": sum(r["observed_tokens"] for r in selected),
            "seconds": sum(r["seconds"] for r in selected)}
    report = {"benchmark": "HX Fresh Domains v1", "created_at": now(), "rows": rows,
              "totals": totals, "planned_trials": len(plan["trials"]), "winner_selected_on_search": "none-fixed-comparison",
              "proposer_tokens": 0, "limitations": [plan["limits"], plan["protocol"]]}
    atomic_write(root / "report.json", canonical(report))
    lines = ["# HX fresh-domain comparison", "", f"Completed: {len(rows)}/{len(plan['trials'])} trials.",
             "", "| Arm | Solved | Observed tokens | Workflow seconds |", "|---|---:|---:|---:|"]
    for arm, total in totals.items():
        lines.append(f"| {arm} | {total['passed']}/{total['n']} | {total['tokens']:,} | {total['seconds']:.1f} |")
    lines += ["", "full = archived core HX; improved = current frozen core HX; single = archived one-shot Luna.",
              "No policy selection or retuning. Read private backend/browser scores separately from readiness."]
    atomic_write(root / "REPORT.md", "\n".join(lines).encode())


def run(root, max_tokens, max_seconds):
    hashes = json.loads((root / "frozen-sha256.json").read_text("utf-8"))
    for path, expected in hashes.items():
        if sha(root / path) != expected:
            raise HXError("frozen source changed: " + path)
    plan = json.loads((root / "plan.json").read_text("utf-8"))
    clock = root / "clock.json"
    if not clock.exists():
        atomic_write(clock, canonical({"start": time.time(), "max_tokens": max_tokens, "max_seconds": max_seconds}))
    envelope = json.loads(clock.read_text("utf-8"))
    if (max_tokens, max_seconds) != (envelope["max_tokens"], envelope["max_seconds"]):
        raise HXError("campaign envelope changed")
    rows = []
    for index, item in enumerate(plan["trials"]):
        score_path = root / "heldout-results" / item["key"] / "score.json"
        if not score_path.exists():
            if sum(r["observed_tokens"] for r in rows) >= max_tokens or time.time() - envelope["start"] >= max_seconds:
                raise HXError("campaign envelope exhausted")
        runtime = root / ("runtime-improved" if item["arm"] == "improved" else "runtime-baseline")
        extra = {"PYTHONPATH": os.pathsep.join([str(runtime / "src"), str(root / "protocol")])}
        if os.environ.get("CODEX_HOME"):
            extra["CODEX_HOME"] = os.environ["CODEX_HOME"]
        print(json.dumps({"event": "case.cached" if score_path.exists() else "case.started", "arm": item["arm"], "case": item["case"]["id"], "repeat": item["repeat"]}), flush=True)
        # Even cached scores pass the frozen trial's identity check before reuse.
        code, _, err = execute([sys.executable, "-m", "benchmarks.fresh.runner", "trial", str(root), str(index)],
            root, clean_env(extra), root / "trial-processes" / (item["key"] + "-" + str(time.time_ns())),
            1500, lambda: None, max_bytes=20000000)
        if code:
            raise HXError("trial controller failed: " + err[-3000:])
        score = json.loads(score_path.read_text("utf-8"))
        rows.append(score)
        write_report(root, plan, rows)
        print(json.dumps({"event": "case.finished", **score}), flush=True)
    atomic_write(root / "complete.json", canonical({"finished": now(), "trials": len(rows)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("directory", type=Path)
    p = sub.add_parser("validate")
    p.add_argument("manifest", type=Path)
    p.add_argument("directory", type=Path)
    p = sub.add_parser("prepare")
    p.add_argument("directory", type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--validation", required=True, type=Path)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--repeats", type=int, default=2)
    p = sub.add_parser("run")
    p.add_argument("directory", type=Path)
    p.add_argument("--max-tokens", type=int, default=15000000)
    p.add_argument("--max-seconds", type=int, default=14400)
    p = sub.add_parser("trial")
    p.add_argument("directory", type=Path)
    p.add_argument("index", type=int)
    args = parser.parse_args()
    settings = load_settings(HERE / "campaign.toml")
    root = args.directory.resolve()
    if args.command == "build":
        build(root)
    elif args.command == "validate":
        return 0 if validate(args.manifest.resolve(), root, settings) else 1
    elif args.command == "prepare":
        prepare(root, args.manifest.resolve(), args.validation.resolve(), args.baseline.resolve(), HERE / "campaign.toml", args.repeats)
    elif args.command == "trial":
        trial(root, args.index)
    else:
        run(root, args.max_tokens, args.max_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
