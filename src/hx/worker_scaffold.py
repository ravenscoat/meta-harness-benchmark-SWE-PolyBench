"""Credential-free executable policy around worker calls and public tools.

The candidate selects actions; this controller alone executes them. It never
allows a candidate to change model, schema, budget, verification or grading.
The restricted code surface is not a general-purpose Python security sandbox.
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from hx.code_search import sha, validate_source
from hx.config import canonical
from hx.models import Contract, HXError, ProcessTimeout
from hx.repo_context import inspect
from hx.store import atomic_write

VERSION = "executable-worker-scaffold@1"
TARGET = "candidate_scaffold.py"
OPTIONAL_CONTEXT = {"selected_source", "tracked_files_prefix", "repository_map", "environment_snapshot"}
MAX_DELEGATES = 2
MAX_INSPECTIONS = 2
MAX_ACTIONS = 5


class Action(Contract):
    action: Literal["inspect", "delegate", "finish"]
    query: str = Field(max_length=2000)
    guidance: str = Field(max_length=4000)
    memory: dict
    context: dict
    omit_optional_context: list[Literal["selected_source", "tracked_files_prefix", "repository_map", "environment_snapshot"]] = Field(max_length=4)


def validate_scaffold(data):
    return validate_source(data, interface="next_action", parameters=("state",))


DRIVER = """import json,runpy,sys
try:
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
 resource.setrlimit(resource.RLIMIT_CPU,(4,4))
except ImportError:
 pass
state=json.load(open(sys.argv[2]))
action=runpy.run_path(sys.argv[1])['next_action'](state)
print(json.dumps(action))
"""


class Planner:
    def __init__(self, source):
        path = Path(source)
        if path.is_symlink():
            raise HXError("Scaffold source must be a regular immutable file")
        self.source = path.resolve()
        data = self.source.read_bytes()
        validate_scaffold(data)
        self.sha256 = sha(data)

    def decide(self, state, directory):
        if sha(self.source.read_bytes()) != self.sha256:
            raise HXError("Scaffold changed after fingerprinting")
        directory.mkdir(parents=True, exist_ok=False)
        payload = canonical(state)
        if len(payload) > 500_000:
            raise HXError("Scaffold state exceeds input bound")
        atomic_write(directory / "state.json", payload)
        environment = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if sys.platform == "win32" else {}
        try:
            result = subprocess.run([sys.executable, "-I", "-c", DRIVER, str(self.source),
                str((directory / "state.json").resolve())], capture_output=True, timeout=5, env=environment)
        except subprocess.TimeoutExpired as error:
            atomic_write(directory / "error.txt", str(error).encode())
            raise HXError("Scaffold decision timed out") from error
        atomic_write(directory / "stdout.txt", result.stdout)
        atomic_write(directory / "stderr.txt", result.stderr)
        if result.returncode or len(result.stdout) > 32_000:
            raise HXError("Scaffold execution failed or exceeded output bound")
        try:
            action = Action.model_validate_json(result.stdout)
        except ValueError as error:
            raise HXError("Scaffold returned an invalid action") from error
        if len(canonical(action.model_dump())) > 24_000:
            raise HXError("Scaffold action context exceeds bound")
        atomic_write(directory / "action.json", canonical(action.model_dump()))
        return action


class WorkerScaffoldAdapter:
    """Opt-in adapter; all delegate calls use the original worker/model/schema."""
    def __init__(self, adapter, source, settings):
        self.delegate = adapter
        self.planner = Planner(source)
        self.settings = settings
        self.name = VERSION
        self.capabilities = adapter.capabilities
        self.headroom = None

    @property
    def workflow_deadline(self):
        return getattr(self.delegate, "workflow_deadline", None)

    @workflow_deadline.setter
    def workflow_deadline(self, value):
        self.delegate.workflow_deadline = value

    def run(self, role, task, workspace, context, instructions, contract, log_dir,
            check_control, emit, timeout):
        if role != "implementer":
            return self.delegate.run(role, task, workspace, context, instructions, contract,
                                     log_dir, check_control, emit, timeout)
        started = time.monotonic()
        state = {"report": task.report, "kind": task.kind,
                 "stage": context.get("stage", "implementation"), "worker_calls": 0,
                 "inspections": 0, "observations": [], "memory": {}, "last_summary": None}
        result = None
        for index in range(MAX_ACTIONS):
            check_control()
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise ProcessTimeout("Scaffold exhausted the shared model-attempt deadline")
            action = self.planner.decide(state, log_dir / ("decision-" + str(index)))
            state["memory"] = action.memory
            emit("scaffold.action", {"index": index, "action": action.action,
                "source_sha256": self.planner.sha256, "worker_calls": state["worker_calls"]})
            if action.action == "finish":
                if result is None:
                    raise HXError("Scaffold cannot finish without a schema-valid worker result")
                atomic_write(log_dir / "result.json", canonical(result))
                return result
            if action.action == "inspect":
                if state["inspections"] >= MAX_INSPECTIONS or not action.query.strip():
                    raise HXError("Scaffold inspection limit or empty query")
                observation = inspect(Path(workspace), action.query, limit=6)
                # The trusted public source tool determines its own read/path bounds.
                # Its inventory is availability, never passing-test evidence.
                state["observations"].append(observation)
                state["inspections"] += 1
                atomic_write(log_dir / ("inspection-" + str(index) + ".json"), canonical(observation))
                emit("scaffold.inspected", {"query": action.query, "matches": len(observation["matches"])})
                continue
            if state["worker_calls"] >= MAX_DELEGATES:
                raise HXError("Scaffold delegate-call limit exceeded")
            check_control()
            if self.headroom is not None and self.headroom() < self.settings.repair_token_reserve:
                raise HXError("Scaffold insufficient token headroom for another worker call")
            # Only explicitly optional source inventories can be omitted. Task,
            # verification, independent challenge and all other contracts persist.
            selected = {k: v for k, v in context.items() if k not in action.omit_optional_context}
            selected["executable_scaffold"] = {"context": action.context,
                "observations": state["observations"], "memory": action.memory,
                "previous_summary": state["last_summary"], "guidance": action.guidance,
                "limitations": "Source discovery is not test evidence. Original verification contracts apply."}
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise ProcessTimeout("Scaffold exhausted the shared model-attempt deadline")
            raw = self.delegate.run(role, task, workspace, selected, instructions, contract,
                log_dir / ("delegate-" + str(state["worker_calls"])), check_control, emit, remaining)
            result = contract.model_validate(raw).model_dump()
            atomic_write(log_dir / "last-worker-result.json", canonical(result))
            state["last_summary"] = result
            state["worker_calls"] += 1
        raise HXError("Scaffold exhausted its action limit without finishing")
