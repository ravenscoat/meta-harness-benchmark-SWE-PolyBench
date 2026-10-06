"""Use a measured context policy with the normal HX evidence and human gates."""

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from benchmarks.advanced.runner import RecoveryVerifier
from hx.adapters import CodexAdapter
from hx.config import digest, load_settings, load_task
from hx.engine import Engine
from hx.git import git
from hx.models import HXError
from hx.optimization import Policy
from hx.store import Store
from hx.verification import Verifier


def selected_policy(campaign: Path, experimental=False) -> Policy:
    if not (campaign / "complete.json").exists():
        raise HXError("campaign has not completed reserved evaluation")
    audit = campaign / "evaluation-audit.json"
    if (
        audit.exists()
        and json.loads(audit.read_text("utf-8")).get("normal_adoption_blocked")
        and not experimental
    ):
        raise HXError(
            "evaluator audit requires further clean evaluation before normal policy adoption"
        )
    selection = json.loads((campaign / "selection.json").read_text("utf-8"))
    report = json.loads((campaign / "report.json").read_text("utf-8"))
    arm = selection["arm"]
    if arm != report["winner_selected_on_search"]:
        raise HXError("selection and report disagree")
    if audit.exists() and not experimental:
        validate_evaluator_audit(campaign, report, arm)
    rows = report["rows"]
    baseline = {
        (r["case"], r["repeat"]): r for r in rows if r["split"] == "heldout" and r["arm"] == "full"
    }
    treatment = {
        (r["case"], r["repeat"]): r for r in rows if r["split"] == "heldout" and r["arm"] == arm
    }
    if not baseline or baseline.keys() != treatment.keys():
        raise HXError("reserved comparison is incomplete")
    interrupted = any(
        "usage limit" in str(row.get("error") or "").lower()
        or "rate limit" in str(row.get("error") or "").lower()
        for row in [*baseline.values(), *treatment.values()]
    )
    if interrupted and not experimental:
        raise HXError(
            "reserved comparison includes provider quota interruptions; further experimental evaluation is required before adoption"
        )
    gain = sum(r["task_success"] for r in treatment.values()) - sum(
        r["task_success"] for r in baseline.values()
    )
    if gain <= 0 and not experimental:
        raise HXError(
            "selected policy did not improve reserved success; use --experimental only for deliberate further evaluation"
        )
    return Policy.model_validate(selection["policy"])


def validate_evaluator_audit(campaign, report, arm):
    metadata = json.loads((campaign / "evaluation-audit.json").read_text("utf-8"))
    try:
        directory = Path(metadata["audit_directory"])
        certificate = directory / "audit.json"
        if hashlib.sha256(certificate.read_bytes()).hexdigest() != metadata["audit_sha"]:
            raise HXError("evaluator audit certificate integrity failed")
        saved = json.loads(certificate.read_text("utf-8"))
        original_sha = hashlib.sha256((campaign / "report.json").read_bytes()).hexdigest()
        if (
            not saved["validated"]
            or not saved["campaign_complete"]
            or saved["original_report_sha"] != original_sha
        ):
            raise HXError("evaluator audit is incomplete or stale")
        program = directory / "compatible_queue.test.jsx"
        if hashlib.sha256(program.read_bytes()).hexdigest() != saved["program_sha"]:
            raise HXError("evaluator audit program integrity failed")
        if saved["original_selected"] != arm or saved["corrected_selected"] != arm:
            raise HXError("evaluator audit changes the selected policy")
        expected = {
            f"{r['arm']}-{r['case']}-{r['repeat']}": r
            for r in report["rows"]
            if "queue" in r.get("acceptance", {}).get("groups", {})
        }
        measured = {r["trial"]: r for r in saved["rows"]}
        if expected.keys() != measured.keys() or len(measured) != len(saved["rows"]):
            raise HXError("evaluator audit omits graded candidates")
        for name, row in expected.items():
            checked = measured[name]
            if (
                checked["original_success"] != row["task_success"]
                or checked["corrected_success"] != row["task_success"]
                or checked["identity"]["commit"] != row["acceptance"]["candidate_commit"]
            ):
                raise HXError("evaluator audit changes measured outcomes")
    except (KeyError, OSError, TypeError) as error:
        raise HXError("evaluator audit proof is missing or invalid") from error


class PolicyAdapter(CodexAdapter):
    def __init__(self, settings, policy, targets=("implementer",)):
        super().__init__(settings)
        self.policy = policy
        self.targets = targets

    def run(self, role, task, workspace, context, *args, **kwargs):
        if role in self.targets:
            if role in {"correctness", "security"}:
                from benchmarks.advanced.runner import review_policy_context

                context = review_policy_context(self.policy, workspace, context)
                return super().run(role, task, workspace, context, *args, **kwargs)
            selected = {}
            for relative in self.policy.context_files:
                path = workspace / relative
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and path.resolve().is_relative_to(workspace.resolve())
                ):
                    selected[relative] = path.read_text("utf-8")[:25000]
            context = {
                **context,
                "harness_guidance": self.policy.instructions,
                "selected_source": selected,
            }
            if self.policy.environment_snapshot:
                context["environment"] = {
                    "python": sys.executable,
                    "files": git(workspace, "ls-files").splitlines(),
                    "frontend": task.frontend,
                    "dependencies": "Installed by the operator; no worker network or package installation.",
                }
        return super().run(role, task, workspace, context, *args, **kwargs)


class PolicyVerifier:
    def __init__(self, settings):
        self.standard = Verifier(settings)
        self.frontend = RecoveryVerifier(settings)

    def run(self, candidate, task, *args, **kwargs):
        verifier = self.frontend if task.frontend else self.standard
        return verifier.run(candidate, task, *args, **kwargs)


class PolicyEngine(Engine):
    def __init__(self, store, settings, policy, targets=("implementer",)):
        if settings.adapter != "codex":
            raise HXError(
                "the policy harness uses real Codex; fake adapter configuration is unsupported"
            )
        super().__init__(store, settings, PolicyAdapter(settings, policy, targets))
        self.verifier = PolicyVerifier(settings)
        self.config["context_policy"] = policy.model_dump()
        self.config["policy_targets"] = list(targets)
        self.config["policy_adapter_sha"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.config["recovery_verifier_sha"] = hashlib.sha256(
            Path(sys.modules[RecoveryVerifier.__module__].__file__).read_bytes()
        ).hexdigest()
        self.config["fingerprint"] = digest(
            {k: v for k, v in self.config.items() if k != "fingerprint"}
        )


def measured_policy_targets(campaign: Path):
    selection = json.loads((campaign / "selection.json").read_text("utf-8"))
    report = json.loads((campaign / "report.json").read_text("utf-8"))
    rows = [r for r in report["rows"] if r["split"] == "search" and r["arm"] == selection["arm"]]
    measured = set()
    if not rows:
        raise HXError("selected arm has no measured search runs")
    for row in rows:
        name = f"{row['arm']}-{row['case']}-{row['repeat']}"
        database = campaign / "search-history" / name / "state" / "state.sqlite3"
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            saved = connection.execute(
                "SELECT body FROM runs WHERE id=?", (row["run_id"],)
            ).fetchone()
        if saved is None:
            raise HXError("selected run provenance is missing")
        config = json.loads(saved[0])["config"]
        fingerprint = digest({k: v for k, v in config.items() if k != "fingerprint"})
        if fingerprint != row["fingerprint"] or fingerprint != config["fingerprint"]:
            raise HXError("selected run configuration integrity failed")
        if config.get("policy") != selection["policy"]:
            raise HXError("selected policy and measured configuration disagree")
        targets = config.get("policy_targets", ["implementer"])
        if (
            not targets
            or len(set(targets)) != len(targets)
            or not set(targets) <= {"implementer", "correctness", "security"}
        ):
            raise HXError("invalid measured policy targets")
        measured.add(tuple(targets))
    if len(measured) != 1:
        raise HXError("selected arm has inconsistent policy targets")
    return next(iter(measured))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(".hx/policy-runs"))
    parser.add_argument("--config", type=Path, default=Path("hx.toml"))
    parser.add_argument("--experimental", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("task", type=Path)
    resume = commands.add_parser("resume")
    resume.add_argument("run_id")
    approve = commands.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("--commit", required=True)
    deny = commands.add_parser("deny")
    deny.add_argument("run_id")
    deny.add_argument("--commit", required=True)
    deny.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        policy = selected_policy(args.campaign, args.experimental)
        targets = measured_policy_targets(args.campaign)
        engine = PolicyEngine(Store(args.state_dir), load_settings(args.config), policy, targets)
        if args.command == "run":
            result = engine.execute(engine.create(load_task(args.task))["id"])
        elif args.command == "resume":
            result = engine.execute(args.run_id, resume=True)
        elif args.command == "approve":
            result = engine.decision(args.run_id, args.commit, True)
        else:
            result = engine.decision(args.run_id, args.commit, False, args.reason)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in {"ready_for_approval", "approved"} else 1
    except (HXError, ValueError, OSError, sqlite3.Error) as error:
        print("HX policy: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
