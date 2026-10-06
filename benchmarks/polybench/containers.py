from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from benchmarks.polybench.dependencies import prepare_dependencies, share_public_fixture
from benchmarks.polybench.test_environment import docker_environment, public_environment
from benchmarks.polybench.worker_environment import build_check, prepare_generated, recipe
from hx.config import canonical
from hx.git import check_baseline_links, git
from hx.models import GateError, HXError
from hx.process import clean_env, execute
from hx.store import atomic_write
from hx.usage import usage_breakdown


def archive(files: dict[str, bytes], uid=0):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            info.uid = info.gid = uid
            tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def read_file(container, path):
    chunks, _ = container.get_archive(path)
    with tarfile.open(fileobj=io.BytesIO(b"".join(chunks))) as tar:
        member = next(m for m in tar.getmembers() if m.isfile())
        return tar.extractfile(member).read()


def command(container, argv, workdir=None, user=None):
    options = {"user": user, "environment": public_environment()} if user else {}
    result = container.exec_run(argv, workdir=workdir, **options)
    if result.exit_code:
        raise HXError("container command failed: " + result.output.decode(errors="replace")[-1800:])
    return result.output


def create(client, case, binary=None, offline=False):
    image = client.images.get(case["image_id"])
    workdir = image.attrs["Config"]["WorkingDir"]
    if workdir not in {"/testbed", "/app"}:
        raise HXError("unsupported image working directory: " + workdir)
    volumes = {str(binary.parent.parent): {"bind": "/opt/hx-cli", "mode": "ro"}} if binary else {}
    if binary:
        # Bind only the tool file. This directory also contains private grader code.
        volumes[str(Path(__file__).with_name("repo_context.py").resolve())] = {
            "bind": "/opt/hx-tools/repo_context.py", "mode": "ro"}
    container = client.containers.create(image.id, command=["/bin/sleep", "infinity"],
        entrypoint=[], working_dir=workdir, network_mode="none" if offline else "bridge",
        volumes=volumes, name="hx-pb-" + uuid.uuid4().hex,
        labels={"hx.benchmark": "polybench-v1"}, cap_drop=["ALL"],
        security_opt=["no-new-privileges"] + (["seccomp=unconfined"] if binary else []),
        mem_limit="6g", nano_cpus=4_000_000_000,
        pids_limit=512)
    container.start()
    return container, workdir


def populate(container, workdir, workspace: Path, case):
    # Image dependencies stay installed. Replace history and overlay the sanitized
    # input repository; no dataset, private tests, Docker socket or host home is mounted.
    command(container, ["git", "-c", "safe.directory=*", "reset", "--hard", case["upstream_base"]], workdir)
    command(container, ["git", "-c", "safe.directory=*", "clean", "-fd"], workdir)
    command(container, ["sh", "-c",
        "git -c safe.directory=* ls-files -z | xargs -0 -r sh -c 'for path in \"$@\"; do if [ ! -d \"$path\" ] || [ -L \"$path\" ]; then rm -f -- \"$path\"; fi; done' sh"], workdir)
    command(container, ["rm", "-rf", "--", workdir + "/.git"])
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        def worker_owned(info):
            # Docker's archive extraction sets ownership without granting the
            # running worker CHOWN. The repository root must also be writable
            # so Codex can create its protected .agents/.codex directories.
            info.uid = info.gid = 1000
            info.uname = info.gname = ""
            info.mode |= 0o200
            return info

        tar.add(workspace, arcname=".", filter=worker_owned)
    if not container.put_archive(workdir, stream.getvalue()):
        raise HXError("candidate transfer failed")
    # Docker preserves the existing extraction root's owner even when tar's
    # root entry has uid 1000. Permit workspace-local creation without CHOWN.
    command(container, ["chmod", "0777", workdir])
    command(container, ["mkdir", "-p", "/tmp/hx-home"])
    command(container, ["chmod", "0777", "/tmp/hx-home"])
    command(container, ["git", "config", "--global", "--add", "safe.directory", workdir],
            user="1000:1000")
    # NTFS archives retain a different uid. This runtime-owned global entry lives
    # outside the writable repository and avoids granting CHOWN to model tools.
    command(container, ["git", "-c", "safe.directory=" + workdir,
                        "config", "--global", "--add", "safe.directory", workdir])
    # Image repository may contain metadata from its build; remove known evaluator files.
    command(container, ["git", "clean", "-f", "--", "patch_code.diff", "patch_test.diff", "eval.sh"], workdir)
    prepare_generated(container, workdir, workspace, case)
    return git(workspace, "rev-parse", "HEAD")


class ContainerAdapter:
    name = "codex-container"
    capabilities = {"streaming": True, "cancel": True, "mid_task_resume": False,
                    "pause": False, "structured_output": True}

    def __init__(self, settings, client, case, binary: Path, auth: Path):
        self.settings, self.client, self.case = settings, client, case
        self.binary, self.auth = binary, auth
        self.workflow_deadline = None
        self.sessions = None  # Opt-in lean runtime; historical runners stay ephemeral.

    def run(self, role, task, workspace, context, instructions, contract, log_dir,
            check_control, emit, timeout):
        started = time.monotonic()
        launched = False
        usage_reported = False
        identifier = None
        session_key = None
        history = None
        check_control()
        container, workdir = create(self.client, self.case, self.binary)
        try:
            prepare_dependencies(container, self.case["repo"], log_dir / "dependencies", self.case["upstream_base"])
            share_public_fixture(container, self.case["repo"])
            input_repo = Path(self.case["repo_path"]) if role == "consolidator" else workspace
            head = populate(container, workdir, input_repo, self.case)
            preflight = build_check(container, workdir, input_repo, self.case,
                log_dir / "worker-preflight", self.settings, check_control, emit)
            if preflight and not preflight.passed:
                raise HXError("Worker environment public build failed before model execution: " + preflight.evidence)
            command(container, ["mkdir", "-p", "/hx", "/hx-auth", "/tmp/hx-home"])
            command(container, ["chmod", "0777", "/hx", "/hx-auth", "/tmp/hx-home"])
            container.put_archive("/hx-auth", archive({"auth.json": self.auth.read_bytes()}, uid=1000))
            container.put_archive("/hx", archive({"schema.json": canonical(contract.model_json_schema())}, uid=1000))
            python = command(container, ["sh", "-c", "command -v python || command -v python3"]).decode().strip()
            inventory = command(container, ["sh", "-c",
                "for tool in git python python3 node npm yarn pnpm pytest rg; do location=$(command -v \"$tool\" || true); printf '%s=%s\\n' \"$tool\" \"$location\"; done"], user="1000:1000").decode()
            context = {**context, "worker_environment": {
                "scope": "Actual worker container; availability is not a successful test result",
                "user": "1000:1000", "working_directory": workdir,
                "tool_paths": dict(line.split("=", 1) for line in inventory.splitlines()),
                "public_test_environment": public_environment(),
                "public_build_recipe": recipe(self.case.get("repo"), input_repo)}}
            emit("tool.worker_environment", context["worker_environment"])
            instructions += (
                "\nOptional read-only navigation tool: " + python +
                " /opt/hx-tools/repo_context.py '<specific query>' --limit 8. "
                "It ranks tracked public source and tests and shows bounded symbol outlines. "
                "JavaScript outlines and ranking are approximate; inspect actual source. "
                "Declared test scripts are discovery hints, not passing test evidence. "
                "Use ordinary focused functional tests; do not submit this tool as verification_commands.\n")
            model = self.settings.judgment_model if role == "consolidator" else self.settings.worker_model
            sandbox = "workspace-write" if role == "implementer" else "read-only"
            if self.sessions is not None and role == 'implementer':
                from benchmarks.polybench.sessions import session_id
                session_key = self.sessions.key(context.get('native_session_scope'), task, model,
                                                contract.model_json_schema(), workdir)
                history = self.sessions.get(session_key, git(workspace, 'rev-parse', 'HEAD^{tree}'))
                if history:
                    identifier = session_id(history.identifier)
                    container.put_archive('/hx-auth', archive(history.files, uid=1000))
                elif context.get('native_session_continuation'):
                    raise GateError('Repair requested without accepted native session history')
                emit('worker.session', {'resumed': history is not None,
                    'session_id': identifier, 'scope': context['native_session_scope'],
                    'history_bytes': sum(len(v) for v in history.files.values()) if history else 0})
            # Generic repository adaptation is identical in all arms; preserve the rest
            # of HX role instructions. These tasks are not necessarily FastAPI apps.
            instructions = instructions.replace(
                "You implement one bounded change in a small FastAPI application, including its React frontend when the task requests it. Implement backend behavior first, then connect and verify the frontend.",
                "Implement one bounded change in the supplied repository, using its actual language, layout and existing interfaces.")
            prompt = instructions + "\n\n<context>\n" + canonical({"task": {
                "id": task.id, "report": task.report, "kind": task.kind,
                "allowed_paths": task.allowed_paths, "protected_paths": task.protected_paths},
                "python_executable": python, "workspace": workdir, **context}).decode() + "\n</context>"
            if history:
                prompt = ('Continue the same task on the exact last delivered source. '
                          'Use the existing session history; repair only from this public feedback. '
                          'Return the same structured output contract.\n' + canonical({
                              'input_commit': head, 'repair_plan': context.get('repair_plan', {}),
                              'working_directory': workdir}).decode())
            atomic_write(log_dir / "prompt.txt", prompt.encode())
            atomic_write(log_dir / "schema.json", canonical(contract.model_json_schema()))
            emit("worker.instantiated", {"role": role, "model": model, "sandbox": sandbox,
                "image": self.case["image_id"], "container": container.id,
                "tools": [{"name": "repo_context", "read_only": True,
                    "sha256": hashlib.sha256(
                        Path(__file__).with_name("repo_context.py").read_bytes()).hexdigest()}]})

            def on_line(line):
                nonlocal usage_reported, identifier
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return
                if not isinstance(event, dict):
                    return
                emit("worker.event", event)
                if session_key and event.get('type') == 'thread.started':
                    from benchmarks.polybench.sessions import session_id
                    observed_id = session_id(event.get('thread_id'))
                    if identifier and observed_id != identifier:
                        raise GateError('Codex resumed a different session')
                    identifier = observed_id
                if event.get("type") == "turn.failed":
                    raise HXError("Codex turn failed: " + str(event.get("error")))
                if event.get("type") == "turn.completed":
                    usage_reported = True
                    usage = event.get("usage", {})
                    emit("worker.usage", {"tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                                          "reported_usage": usage, 'breakdown': usage_breakdown(usage),
                                          'role': role, 'resumed': history is not None})

            from benchmarks.polybench.sessions import codex_arguments
            argv = ["docker", "exec", "-i", "-u", "1000:1000", "-w", workdir,
                *docker_environment(), "-e", "CODEX_HOME=/hx-auth", container.id,
                *codex_arguments(model, sandbox, self.settings.reasoning_effort, workdir,
                                 identifier if history else None, persistent=session_key is not None)]
            check_control()
            preparation_seconds = time.monotonic() - started
            model_timeout = model_window(timeout, self.workflow_deadline, time.monotonic(), preparation_seconds)
            emit("worker.execution_budget", {"preparation_seconds": preparation_seconds,
                "model_timeout_seconds": model_timeout, "workflow_deadline_enforced": self.workflow_deadline is not None})
            launched = True
            code, _, err = execute(argv, workspace, clean_env(), log_dir,
                                   model_timeout,
                                   check_control, on_line, prompt, self.settings.max_log_bytes)
            if code:
                raise HXError(f"container Codex exited {code}: {err[-2000:]}")
            result = read_file(container, "/hx/result.json")
            contract.model_validate_json(result)
            atomic_write(log_dir / "result.json", result)
            if command(container, ["git", "rev-parse", "HEAD"], workdir).decode().strip() != head:
                raise GateError("worker changed Git history")
            if command(container, ["git", "remote"], workdir).strip():
                raise GateError("worker added a Git remote")
            command(container, ["git", "-c", "core.hooksPath=/dev/null", "add", "--all"], workdir, user="1000:1000")
            patch = command(container, ["git", "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD"], workdir)
            if role != "implementer" and patch:
                raise GateError("reviewer changed candidate")
            if patch:
                atomic_write(log_dir / "container.patch", patch)
                completed = subprocess.run(["git", "-C", str(workspace), "apply", "--binary", "--whitespace=nowarn", "-"],
                                           input=patch, capture_output=True, timeout=30)
                if completed.returncode:
                    raise GateError("worker patch transfer failed: " + completed.stderr.decode(errors="replace")[-1500:])
            if session_key:
                from benchmarks.polybench.sessions import history_files
                chunks, _ = container.get_archive('/hx-auth/sessions')
                files = history_files(chunks, identifier)
                tree = command(container, ['git', 'write-tree'], workdir, user='1000:1000').decode().strip()
                self.sessions.save(session_key, identifier, tree, files)
                # Only rollouts are exported. No auth/config/provider files.
                for name, data in files.items():
                    atomic_write(log_dir / 'native-history' / name, data)
                emit('worker.session_saved', {'session_id': identifier, 'source_tree': tree,
                    'files': list(files), 'history_bytes': sum(len(v) for v in files.values())})
            return json.loads(result)
        except Exception as exc:
            if session_key:
                self.sessions.invalidate(session_key)
            # A diagnostic draft is never applied to the host or accepted as a
            # candidate. Capture before container deletion, with its own small
            # cleanup deadline. Concurrent worker writes make it untrusted.
            if role == "implementer" and launched:
                retain_interrupted_draft(container, workdir, workspace, log_dir, emit, exc, usage_reported,
                    ["candidate_scaffold.py"] if self.case["repo"] == "hx/worker-scaffold" else None)
            raise
        finally:
            # Cancel/deadline must kill remote work too, not just docker exec's client.
            container.remove(force=True)


def model_window(timeout, workflow_deadline, now, preparation_seconds):
    # Model time starts after setup, but still fits inside the global workflow.
    remaining = workflow_deadline - now if workflow_deadline is not None else timeout - preparation_seconds
    if remaining <= 0:
        raise HXError("Workflow deadline exhausted during worker preparation")
    return min(timeout, remaining)


def retain_interrupted_draft(container, workdir, workspace, logs, emit, error, usage_known=False, paths=None):
    cleanup_deadline = time.monotonic() + 30
    def remaining():
        value = cleanup_deadline - time.monotonic()
        if value <= 0:
            raise HXError("Diagnostic cleanup deadline exhausted")
        return value
    record = {"accepted": False, "usage_known": usage_known, "error": str(error),
              "limitation": "Diagnostic draft only; no completed contract or verification. May reflect concurrent writes."}
    pathspec = paths if paths is not None else [".", ":(exclude)node_modules",
        ":(glob,exclude)**/node_modules/**", ":(exclude).venv", ":(glob,exclude)**/__pycache__/**"]
    record["diagnostic_paths"] = pathspec
    try:
        argv = ["docker", "exec", "-u", "1000:1000", *docker_environment(), "-w", workdir, container.id,
                "git", "-c", "safe.directory=" + workdir, "-c", "core.hooksPath=/dev/null", "add", "--all",
                "--", *pathspec]
        code, _, _ = execute(argv, workspace, clean_env(), logs / "draft-stage", remaining(), lambda: None,
                             max_bytes=100000)
        if code:
            raise HXError("Diagnostic staging failed")
        argv = ["docker", "exec", "-u", "1000:1000", *docker_environment(), "-w", workdir, container.id,
                "git", "-c", "safe.directory=" + workdir, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD",
                "--", *pathspec]
        code, out, _ = execute(argv, workspace, clean_env(), logs / "draft-export", remaining(),
                             lambda: None, max_bytes=2_000_000)
        if code:
            raise HXError("Diagnostic export failed")
        atomic_write(logs / "interrupted-draft.patch", out.encode())
        record.update(patch_sha256=hashlib.sha256(out.encode()).hexdigest(), bytes=len(out.encode()))
    except Exception as export_error:
        record["export_error"] = str(export_error)
    atomic_write(logs / "interrupted-draft.json", canonical(record))
    emit("worker.interrupted_draft", record)


def extract_base(client, case, destination: Path):
    container, workdir = create(client, case, offline=True)
    try:
        tree = command(container, ["git", "-c", "safe.directory=*", "ls-tree", "-r", "-z", case["upstream_base"]], workdir)
        gitlinks = [row.split(b"\t", 1) for row in tree.split(b"\0") if row.startswith(b"160000 ")]
        payload = command(container, ["git", "-c", "safe.directory=*", "archive", "--format=tar", case["upstream_base"]], workdir)
        destination.mkdir(parents=True, exist_ok=False)
        with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
            tar.extractall(destination, filter="data")
        subprocess.run(["git", "init", "-q", str(destination)], check=True)
        git(destination, "config", "user.name", "HX Runtime")
        git(destination, "config", "user.email", "hx@localhost")
        # Initialization is infrastructure work, before model budgets start.
        # Large snapshots on WSL's Windows mount can exceed the core 30s limit.
        commands = [("add", "--all", "--force")]
        for metadata, name in gitlinks:
            commands.append(("update-index", "--add", "--cacheinfo", "160000",
                             metadata.split()[2].decode(), name.decode()))
        commands.append(("commit", "-qm", "Sanitized benchmark base"))
        for args in commands:
            subprocess.run(["git", "-c", "safe.directory=" + str(destination.resolve()),
                            "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                            "-c", "core.autocrlf=false", "-C", str(destination), *args],
                           check=True, capture_output=True, timeout=300)
        base = git(destination, "rev-parse", "HEAD")
        check_baseline_links(destination, base)
        original_tree = command(container, ["git", "rev-parse", case["upstream_base"] + "^{tree}"], workdir).decode().strip()
        if git(destination, "rev-parse", base + "^{tree}") != original_tree:
            raise HXError("sanitized benchmark source tree differs from upstream")
        return base
    finally:
        container.remove(force=True)
