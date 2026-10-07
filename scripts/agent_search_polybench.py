"""Opt-in live backend for measured search over already-prepared PolyBench cases.

Config via HX_AGENT_SEARCH_CONFIG: prepared_root, private_root, carrier_case,
proposal_seconds. No task/image preparation or automatic historical reruns.
All private working/grading artifacts stay outside the public search archive.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from benchmarks.polybench import runner
from benchmarks.polybench.lean import LeanEngine
from hx.agent_search import Proposal, Trial
from hx.code_search import CodeProposal, copy_experience, seal, sha
from hx.config import canonical, digest
from hx.git import git
from hx.models import HXError, Task
from hx.store import atomic_write
from hx.worker_scaffold import WorkerScaffoldAdapter
from scripts.overnight_limits import account_usage, can_start


class PolyBenchBackend:
    def __init__(self, config_path):
        self.config_path = config_path.resolve()
        self.config = json.loads(config_path.read_text())
        self.prepared = Path(self.config["prepared_root"]).resolve()
        self.private = Path(self.config["private_root"]).resolve()
        if self.private.exists():
            raise HXError("New private search root required")
        self.private.mkdir(parents=True)
        self.counter = 0

    def admit(self, plan):
        required = [self.config_path, Path(__file__).resolve(),
                    self.prepared / "dataset.csv", self.prepared / "selection.json",
                    self.prepared / "images.json", self.prepared / "settings.toml",
                    self.prepared / "storage.json"]
        for case in plan.development + plan.heldout:
            provenance = self.config.get("case_provenance", {}).get(case)
            if (not provenance or provenance.get("reference_informed") is not False
                    or (case in plan.heldout and provenance.get("previous_coding_exposure") is not False)):
                raise HXError("Explicit independent case provenance required: " + case)
            required += [self.prepared / "public" / (case + ".json"),
                         self.prepared / "preflight" / case / "validation.json"]
        required += list(Path("src/hx").glob("*.py"))
        required += list(Path("src/hx/prompts").glob("*.md"))
        required += list(Path("src/hx/scaffolds").glob("*.py"))
        required += list(Path("benchmarks/polybench").glob("*.py"))
        required += list((runner.VENDOR / "src").rglob("*.py"))
        required += [runner.BINARY, Path("scripts/overnight_limits.py"),
                     Path("scripts/run_agent_search.py")]
        for path in required:
            if plan.source_locks.get(str(path.resolve())) != sha(path.read_bytes()):
                raise HXError("Required live backend input is not locked: " + str(path))
        _, _, client, settings = runner.resources(self.prepared)
        client.close()
        for case in plan.development + plan.heldout:
            receipt = json.loads((self.prepared / "preflight" / case / "validation.json").read_text())
            if not receipt.get("valid"):
                raise HXError("All selected reference/environment gates must pass before coding")
        if (settings.worker_model != plan.model or settings.reasoning_effort != plan.reasoning_effort
                or settings.workflow != "single" or settings.max_revisions > 1):
            raise HXError("Live backend requires fixed single-solver settings and at most one repair")
        quota = account_usage(runner.BINARY, runner.AUTH)
        if not can_start(quota):
            raise HXError("Ordinary quota admission blocked; no purchases or reset redemption")
        if shutil.disk_usage(Path.cwd()).free < 40 * 1024**3:
            raise HXError("40 GiB host storage guard blocked admission")

    def evaluate(self, source, case, repeat, directory, plan, control):
        # Engine snapshot discovers the CLI by name even though the container
        # adapter uses the pinned absolute binary. Apply the same launch setup
        # as the existing benchmark controllers before creating an identity.
        os.environ["PATH"] = str(runner.BINARY.parent) + os.pathsep + os.environ.get("PATH", "")
        self.counter += 1
        trial_root = self.private / f"trial-{self.counter}"
        trial_root.mkdir()
        if trial_root.is_relative_to(directory.parent.parent):
            raise HXError("Private trial root must be outside public archive")
        for name in ("dataset.csv", "selection.json", "images.json", "settings.toml", "storage.json"):
            shutil.copyfile(self.prepared / name, trial_root / name)
        # A task-local ledger retains only its pinned image, even when the
        # search preparation contains several development/reserved cases.
        images = json.loads((trial_root / "images.json").read_text())
        selection = json.loads((trial_root / "selection.json").read_text())
        if case in images:
            atomic_write(trial_root / "images.json", canonical({case: images[case]}))
            selection["cases"] = [c for c in selection["cases"] if c["id"] == case]
            atomic_write(trial_root / "selection.json", canonical(selection))
        shutil.copytree(self.prepared / "public", trial_root / "public")
        shutil.copytree(self.prepared / "preflight", trial_root / "preflight")
        (trial_root / "experiments").mkdir()
        # Each root is a fresh identity, even for repeated development cases.
        scaffold = trial_root / "search-scaffold.py"
        scaffold.write_bytes(source.read_bytes())
        backend = self

        class SearchLean(LeanEngine):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.adapter = WorkerScaffoldAdapter(self.adapter, scaffold, self.settings)
                self.config["search_scaffold_sha256"] = sha(scaffold.read_bytes())
                self.config["search_trial_root"] = str(trial_root)
                self.config["fingerprint"] = digest({k: v for k, v in self.config.items() if k != "fingerprint"})

            def check_control(self, *args, **kwargs):
                control()
                return super().check_control(*args, **kwargs)

            def _worker(self, *args, **kwargs):
                control(plan.trial_token_headroom)
                backend.admit(plan)
                return super()._worker(*args, **kwargs)

        score = runner.run_case(trial_root, case, "lean", start_guard=control, engine_factory=SearchLean)
        # Export only explicitly public implementation/verification evidence.
        state = trial_root / "experiments"
        sources = {}
        for path in state.rglob("*"):
            parts = path.relative_to(state).parts
            if "private-evaluation" in parts or not path.is_file() or path.is_symlink():
                continue
            if "steps" in parts and path.name in {"prompt.txt", "stdout.txt", "stderr.txt"}:
                sources[path.relative_to(state).as_posix()] = path
        copy_experience(directory / "public-traces", sources)
        return Trial(identity=score["identity"], case=case, repeat=repeat,
                     source_sha256=sha(source.read_bytes()), model=plan.model,
                     reasoning_effort=plan.reasoning_effort,
                     official_resolved=score["official_resolved"], public_verified=score["visible_verified"],
                     usage_known=score["usage_known"], reported_tokens=score["observed_tokens"],
                     seconds=score["seconds"], infrastructure_error=score["grader_error"],
                     patch_error=score["candidate_patch_error"],
                     missing_observations=score["unobserved_acceptance_tests"],
                     accepted_candidate=bool(score["acceptance"].get("candidate_commit")),
                     workflow_error=score.get('error'), workflow_status=score.get('status'),
                     reference_informed=False)

    def propose(self, public_archive, directory, plan, control):
        from benchmarks.polybench.containers import ContainerAdapter

        self.admit(plan)
        _, images, client, settings = runner.resources(self.prepared)
        tokens = 0

        def emit(kind, data):
            nonlocal tokens
            if kind == "worker.usage":
                tokens += int(data["tokens"])
            with (directory / "events.jsonl").open("ab") as stream:
                stream.write(canonical({"kind": kind, "data": data}) + b"\n")

        try:
            with tempfile.TemporaryDirectory(prefix="hx-agent-proposer-", dir=self.private) as temporary:
                workspace = Path(temporary) / "workspace"
                workspace.mkdir()
                copy_experience(workspace / "experience", {
                    p.relative_to(public_archive).as_posix(): p
                    for p in public_archive.rglob("*") if p.is_file()})
                references = {name: Path(name) for name in
                              ("src/hx/worker_scaffold.py", "src/hx/scaffolds/single_call.py")}
                copy_experience(workspace / "reference", references)
                target = workspace / "candidate_scaffold.py"
                target.write_bytes((public_archive / "baseline.py").read_bytes())
                git(workspace, "init")
                git(workspace, "add", ".")
                git(workspace, "-c", "user.name=HX", "-c", "user.email=hx@local", "commit", "-qm", "Search inputs")
                before = {k: v for k, v in seal(workspace).items() if not k.startswith(".git/")}
                carrier = {**images[self.config["carrier_case"]], "repo": "hx/worker-scaffold",
                           "repo_path": str(workspace)}
                adapter = ContainerAdapter(settings, client, carrier, runner.BINARY, runner.AUTH)
                instructions = (
                    "Optimize one reusable agent program in candidate_scaffold.py. Read reference/ and "
                    "experience/ selectively, starting with diagnosis-*.json: prior executable code, aggregate official scores and public "
                    "traces. Preserve next_action(state) and the six-field Action interface. Change ONLY "
                    "that file. Improve exploration/context or repair decisions across tasks, never hardcode "
                    "case IDs or solutions. Ground the diagnosis in inspected public evidence; do not infer "
                    "private failed assertions or hide failing compatibility tests. Compare workflow defects "
                    "with behavioral non-solves and propose a general mechanism. Do not change budgets, models, graders or contracts. No network, "
                    "models, evaluations or tests. Only import re; no filesystem IO/reflection/dynamic code "
                    "in the candidate. Return diagnosis, inspected_files, change and limitations. External "
                    "evaluation alone decides correctness and adoption.")
                metadata = adapter.run("implementer", Task(id="agent-search-proposer", repo=str(workspace),
                    report="Propose a reusable executable agent from development evidence.",
                    allowed_paths=["candidate_scaffold.py"], protected_paths=["reference/**", "experience/**"]), workspace,
                    {}, instructions, CodeProposal, directory / "model", control, emit,
                    int(self.config["proposal_seconds"]))
                after = {k: v for k, v in seal(workspace).items() if not k.startswith(".git/")}
                if {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)} != {"candidate_scaffold.py"}:
                    raise HXError("Proposer changed protected inputs or made no source change")
                atomic_write(directory / "diagnosis.json", canonical(metadata))
                return Proposal(source=target.read_text(), hypothesis=metadata["diagnosis"],
                                reported_tokens=tokens, usage_known=True)
        finally:
            client.close()


def create_backend():
    return PolyBenchBackend(Path(os.environ["HX_AGENT_SEARCH_CONFIG"]))
