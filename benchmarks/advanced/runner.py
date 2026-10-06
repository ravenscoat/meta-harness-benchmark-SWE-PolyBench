"""Trusted extension for original synchronization-feature challenges.

Keep this outside the running v1 runtime. Every extension asset is fingerprinted
in the manifest and effective run configuration. No generated Python is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import hx.optimization as optimization
from hx.challenge_checks import BACKEND
from hx.challenge_eval import grade as base_grade
from hx.challenge_eval import npm_command, prepare_frontend
from hx.challenge_suite import ASSETS
from hx.config import canonical, digest, load_settings, load_task
from hx.git import assert_clean, clone, derive, git
from hx.models import Candidate, Check, HXError, Task, Verification
from hx.process import clean_env, execute
from hx.store import atomic_write

HERE = Path(__file__).resolve().parent
API_SPEC = """Add POST /sync with X-Tenant and JSON {operations:[{mutation_id,item_id,expected_version,title}]}. Validate the entire request before mutating: 1..50 operations, unique nonempty mutation IDs <=80 characters, positive integer item/version, nonblank titles <=120 characters. Missing tenant401, invalid request422. Return HTTP200 {results:[...]} in request order. Each result contains mutation_id and status:200 with item after one version increment/audit;412 with current owned item for stale version;404 with no item for missing/foreign IDs;409 with no item when a tenant/mutation_id is reused for different content. Exact operation replay returns its original result, including original conflict snapshots, with no new mutation/audit, across process restarts. IDs are independent across tenants. Apply valid independent operations even when another returns a conflict/not-found. Commit batch changes and replay records atomically; concurrent retries cannot double apply; concurrent distinct writes based on one version have exactly one winner. Preserve existing endpoints."""
QUEUE_SPEC = """Create frontend/src/queue.jsx exporting useSyncQueue({tenant,send,storage=localStorage}). Return {pending,working,error,enqueue,discard,flush}. pending contains operations matching /sync; send(operations,tenant) returns Promise<{results}>. enqueue validates and durably stores under hx-outbox:<tenant> BEFORE exposing state; identical mutation ID/content is a no-op, changed content with same ID throws. Ignore corrupt stored queues; storage failure must not create phantom entries. flush is single-flight (same Promise for concurrent calls) and explicitly initiated, never auto-send. Batch at most50 and at most one operation per item. On200 remove only acknowledged operations and rebase later unsent same-item operations from the just-applied expected version to returned version. New enqueues during a send must survive and then drain. Validate complete unique acknowledgements and item ID/version before removing anything; malformed replies preserve the whole in-flight batch. Valid non200 results remain queued and stop flushing with an error; successful independent results are removed. Network rejection preserves durable state and permits explicit retry with the same mutation IDs. discard removes a specified pending ID when idle, enabling conflict recovery. Reload restores the queue. Tenant changes immediately expose only the new tenant queue; obsolete tenant/unmounted completions must not mutate state OR either tenant's persisted queue. React StrictMode must not duplicate sends or lose state. Keep existing hook exports and UI behavior."""
QUEUE_SPEC = (
    "Wire contract: each operation is {mutation_id,item_id,expected_version,title}. "
    "mutation_id is a nonempty string <=80 characters; item_id and expected_version "
    "are positive integers; title is a nonblank string <=120 characters. Use these "
    "snake_case names in enqueue, pending, persisted operations and send arguments. "
    "send(operations,tenant) returns Promise<{results:[{mutation_id,status,item?}]}>. "
    "status is 200,412,404,409; 200/412 include an item with matching numeric id, "
    "positive integer version and title, while 404/409 have no item. The standalone "
    "outbox task implements the hook only: supplied send abstracts the server.\n\n"
    "error is null when clear and a nonempty message string on a failed flush; "
    "network errors retain the original Error.message. flush handles network, "
    "acknowledgement and persistence failures internally and resolves when stopped, "
    "with pending work preserved and working false. Synchronous enqueue/discard "
    "storage failures propagate the original storage exception to the caller, "
    "without publishing an unpersisted change.\n\n" + QUEUE_SPEC
)
CASES = {
    "delta-api": ("search", ["delta", "delta_concurrent"], API_SPEC),
    "durable-outbox": ("search", ["queue"], QUEUE_SPEC),
    "fullstack-sync": (
        "heldout",
        ["delta", "delta_concurrent", "queue"],
        API_SPEC + "\n\n" + QUEUE_SPEC,
    ),
    "sync-recovery": (
        "heldout",
        ["delta", "delta_concurrent", "queue"],
        "Implement synchronization and recovery after dropped responses, process reloads, multiple tabs/clients and tenant switches. Add adversarial regression tests for malformed acknowledgements, storage failures, repeated saves and concurrent server replay.\n"
        + API_SPEC
        + "\n\n"
        + QUEUE_SPEC,
    ),
}


def extension_hash():
    paths = [
        *sorted(HERE.glob("*.py")),
        *sorted(HERE.glob("*.jsx")),
        (ASSETS / "backend_reference.py"),
        *sorted((ASSETS / "fullstack/src").glob("*")),
        (ASSETS / "fullstack/package-lock.json"),
    ]
    return digest(
        {
            str(p.relative_to(ASSETS)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
            if p.is_file()
        }
    )


def build(directory):
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise HXError("advanced suite directory must be empty")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "hx-sync-features-v1",
        "extension_sha": extension_hash(),
        "cases": [],
        "source": "original synthetic feature tasks; not public benchmark scores",
    }
    for name, (split, groups, report) in CASES.items():
        repo = directory / "repos" / name
        (repo / "backend").mkdir(parents=True)
        (repo / "tests").mkdir()
        shutil.copytree(
            ASSETS / "fullstack",
            repo / "frontend",
            ignore=shutil.ignore_patterns("node_modules", "dist"),
        )
        (repo / "backend/__init__.py").write_text("", "utf-8")
        (repo / "backend/app.py").write_bytes((ASSETS / "backend_reference.py").read_bytes())
        (repo / ".gitignore").write_text(
            "__pycache__/\n.pytest_cache/\n.coverage*\n*.sqlite3\nnode_modules/\ndist/\n", "utf-8"
        )
        (repo / "tests/test_existing.py").write_text(
            "from fastapi.testclient import TestClient\nfrom backend.app import app\n\ndef test_health():\n    assert TestClient(app).get('/health').json()=={'ok':True}\n",
            "utf-8",
        )
        (repo / "README.md").write_text(
            "Transactional workspace. Backend: backend/app.py; HX_DB configures SQLite. React: frontend/src/hooks.jsx, new queue hook belongs in frontend/src/queue.jsx. Existing card creation supports X-Tenant and Idempotency-Key; PATCH requires If-Match. Dependencies preinstalled. Run supplied Python executable -m pytest; frontend npm test -- --maxWorkers=1 and npm run build. Do not change dependency manifests.\n",
            "utf-8",
        )
        git(repo, "init")
        git(repo, "config", "user.name", "HX Benchmark")
        git(repo, "config", "user.email", "hx@localhost")
        git(repo, "add", "--all")
        git(repo, "commit", "--quiet", "-m", "Synchronization feature baseline")
        task = Task(
            id=name,
            repo=str(repo),
            report=report,
            kind="feature",
            frontend=True,
            base_commit=git(repo, "rev-parse", "HEAD"),
            allowed_paths=["backend/**", "tests/**", "frontend/src/**"],
            protected_paths=["tests/test_existing.py", "frontend/src/existing.test.jsx"],
        )
        path = directory / "tasks" / split / (name + ".json")
        atomic_write(path, canonical(task.model_dump()))
        manifest["cases"].append(
            {
                "id": name,
                "split": split,
                "groups": groups,
                "task": str(path),
                "base_commit": task.base_commit,
                "task_sha256": digest(task.model_dump()),
                "extension_sha": manifest["extension_sha"],
            }
        )
    manifest["fingerprint"] = digest(manifest)
    path = directory / "manifest.json"
    atomic_write(path, canonical(manifest))
    return path


def acceptance_command(*args, **kwargs):
    try:
        return execute(*args, **kwargs)
    except HXError as error:
        if not str(error).startswith(
            (
                "process timed out",
                "process log budget exceeded",
                "child process left an output pipe open",
            )
        ):
            raise
        return 1, "", str(error)


def grade(candidate, groups, directory, settings):
    if not set(groups).intersection({"delta", "delta_concurrent", "queue"}):
        return base_grade(candidate, groups, directory, settings)
    if not set(groups) <= {"delta", "delta_concurrent", "queue"}:
        raise HXError("unknown advanced acceptance group")
    repo = clone(Path(candidate.workspace), directory / "workspace", candidate.candidate_commit)
    prepare_frontend(repo, directory / "dependencies")
    temp = directory / "tmp"
    temp.mkdir()
    env = clean_env({"PYTHONPATH": str(repo), "TMP": str(temp), "TEMP": str(temp)})
    results = {}
    for group in groups:
        if group == "queue":
            path = repo / "frontend/__hx_acceptance.test.jsx"
            path.write_bytes((HERE / "private_queue.test.jsx").read_bytes())
            try:
                code, _, _ = acceptance_command(
                    npm_command(
                        "exec", "--", "vitest", "run", "__hx_acceptance.test.jsx", "--maxWorkers=1"
                    ),
                    repo / "frontend",
                    env,
                    directory / group,
                    settings.verification_timeout_seconds,
                    lambda: None,
                )
            finally:
                path.unlink(missing_ok=True)
        else:
            program = (
                BACKEND
                + "\n"
                + (HERE / "private_backend.py").read_text("utf-8")
                + f"\ntest_{group}()\n"
            )
            code, _, _ = acceptance_command(
                [sys.executable, "-c", program],
                repo,
                clean_env({**env, "HX_DB": str(directory / (group + ".sqlite3"))}),
                directory / group,
                settings.verification_timeout_seconds,
                lambda: None,
            )
        results[group] = code == 0
    assert_clean(repo, candidate.candidate_commit)
    return {
        "passed": all(results.values()),
        "groups": results,
        "candidate_commit": candidate.candidate_commit,
    }


class AdvancedEngine(optimization.ChallengeEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config["extension_sha"] = extension_hash()
        self.config["policy_targets"] = ["implementer", "correctness", "security"]
        self.verifier = RecoveryVerifier(self.settings)
        self.config["fingerprint"] = digest(
            {k: v for k, v in self.config.items() if k != "fingerprint"}
        )

    def _worker(
        self, run_id, step_id, role, task, workspace, context, contract, directory, deadline
    ):
        if role in {"correctness", "security"}:
            context = review_policy_context(self.policy, workspace, context)
        return super()._worker(
            run_id, step_id, role, task, workspace, context, contract, directory, deadline
        )


def review_policy_context(policy, workspace, context):
    result = {
        **context,
        "harness_guidance": policy.instructions,
        "selected_source": {
            p: (workspace / p).read_text("utf-8")[:25000] for p in policy.context_files
        },
    }
    if policy.environment_snapshot:
        result["environment"] = {
            "python": sys.executable,
            "files": git(workspace, "ls-files").splitlines(),
            "permission": "Read-only review; guidance cannot authorize edits or bypass gates.",
        }
    return result


class RecoveryVerifier:
    """A bounded test timeout becomes repair feedback; cancellation still propagates."""

    def __init__(self, settings):
        self.settings = settings

    def run(self, candidate, task, directory, check_control, emit):
        repo = clone(Path(candidate.workspace), directory / "workspace", candidate.candidate_commit)
        prepare_frontend(repo, directory / "dependencies", check_control)
        temp = directory / "tmp"
        temp.mkdir()
        env = clean_env(
            {
                "PYTHONPATH": str(repo),
                "HX_DB": str(directory / "visible.sqlite3"),
                "TMP": str(temp),
                "TEMP": str(temp),
            }
        )
        checks = []
        commands = [
            (
                "backend_tests",
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
                repo,
            ),
            ("react_tests", npm_command("test", "--", "--maxWorkers=1"), repo / "frontend"),
            ("react_build", npm_command("run", "build"), repo / "frontend"),
        ]
        for name, argv, cwd in commands:
            try:
                code, out, err = execute(
                    argv,
                    cwd,
                    env,
                    directory / name,
                    self.settings.verification_timeout_seconds,
                    check_control,
                    max_bytes=self.settings.max_log_bytes,
                )
                evidence = (out + err)[-5000:]
            except HXError as failure:
                if not str(failure).startswith("process timed out"):
                    raise
                code = 1
                evidence = (
                    str(failure)
                    + "; inspect tests for hangs, unstable React hook input identities or unresolved promises."
                )
            checks.append(Check(name=name, passed=code == 0, evidence=evidence))
            emit("verification.check", {"name": name, "passed": code == 0})
        assert_clean(repo, candidate.candidate_commit)
        return Verification(
            candidate_commit=candidate.candidate_commit,
            passed=all(c.passed for c in checks),
            checks=checks,
            changed_line_coverage=None,
            known_gaps=["Independent acceptance is evaluated after the workflow."],
        )


def validate(manifest_path, directory, settings):
    manifest = json.loads(manifest_path.read_text("utf-8"))
    rows = []
    directory = directory.resolve()
    for case in manifest["cases"]:
        task = load_task(Path(case["task"]))
        base = task.base_commit
        seed = Candidate(
            base_commit=base,
            input_commit=base,
            candidate_commit=base,
            changed_files=[],
            workspace=task.repo,
            diff_sha256=hashlib.sha256(b"").hexdigest(),
        )
        seeded = grade(seed, case["groups"], directory / case["id"] / "seeded", settings)
        repo = clone(Path(task.repo), directory / case["id"] / "gold", base)
        (repo / "backend/app.py").write_text(
            (ASSETS / "backend_reference.py").read_text("utf-8")
            + "\n"
            + (HERE / "backend_feature.py").read_text("utf-8"),
            "utf-8",
        )
        (repo / "frontend/src/queue.jsx").write_bytes((HERE / "queue_reference.jsx").read_bytes())
        gold = derive(repo, base, base, task)
        accepted = grade(gold, case["groups"], directory / case["id"] / "reference", settings)
        visible = optimization.FullstackVerifier(settings).run(
            gold, task, directory / case["id"] / "visible", lambda: None, lambda *_: None
        )
        row = {
            "case": case["id"],
            "split": case["split"],
            "seeded": seeded,
            "reference": accepted,
            "visible": visible.passed,
            "valid": not seeded["passed"] and accepted["passed"] and visible.passed,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    result = {
        "valid": all(r["valid"] for r in rows),
        "manifest": manifest["fingerprint"],
        "rows": rows,
    }
    atomic_write(manifest_path.parent / "validation.json", canonical(result))
    atomic_write(directory / "validation.json", canonical(result))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "validate", "run"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("benchmarks/campaign.toml"))
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=12000000)
    parser.add_argument("--max-seconds", type=int, default=14400)
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.command == "build":
        print(build(args.directory))
        return
    if not args.manifest:
        parser.error("--manifest required")
    manifest = json.loads(args.manifest.read_text("utf-8"))
    if manifest["extension_sha"] != extension_hash():
        raise HXError("advanced extension changed: rebuild/revalidate before running")
    if args.command == "validate":
        result = validate(args.manifest, args.directory, settings)
        if not result["valid"]:
            raise HXError("reference validation failed")
    else:
        optimization.ChallengeEngine = AdvancedEngine
        optimization.grade = grade
        optimization.campaign(
            args.manifest,
            args.directory,
            settings,
            args.iterations,
            args.repeats,
            max_tokens=args.max_tokens,
            max_seconds=args.max_seconds,
        )


if __name__ == "__main__":
    main()
