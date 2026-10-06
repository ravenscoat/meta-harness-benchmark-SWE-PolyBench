"""One fresh inexpensive Luna FastAPI smoke attempt; preserve every outcome."""
import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from benchmarks.polybench.runner import AUTH, BINARY
from hx.config import canonical, load_settings, load_task
from hx.demo import initialize
from hx.engine import Engine
from hx.store import Store, atomic_write
from scripts.overnight_limits import account_usage, can_start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.exists():
        raise RuntimeError("Use a new identity; no scored smoke reruns")
    root.mkdir()
    usage = account_usage(BINARY, AUTH)
    atomic_write(root / "quota.json", canonical(usage))
    if not can_start(usage):
        raise RuntimeError("Quota blocks model work; no credits redeemed")
    native = Path("/opt/hx-polybench-runtime/v1/state") / root.name
    native.mkdir(exist_ok=False)
    settings = load_settings(Path("hx.toml")).model_copy(update={
        "adapter": "codex", "workflow": "single", "max_observed_tokens": 120000,
        "max_attempts": 1, "max_revisions": 1, "attempt_timeout_seconds": 120,
        "run_timeout_seconds": 360})
    atomic_write(root / "settings.json", canonical(settings.model_dump()))
    task_path = next(p for p in initialize(native / "fixture") if p.stem == "missing-task")
    with tempfile.TemporaryDirectory(prefix="hx-live-auth-",
            dir="/opt/hx-polybench-runtime/v1/infra-checks") as auth_home:
        copied_auth = Path(auth_home) / "auth.json"
        shutil.copyfile(AUTH, copied_auth)
        copied_auth.chmod(0o600)
        old_path, old_home = os.environ.get("PATH", ""), os.environ.get("CODEX_HOME")
        os.environ["PATH"] = str(BINARY.parent) + os.pathsep + old_path
        os.environ["CODEX_HOME"] = auth_home
        try:
            engine = Engine(Store(native / "state"), settings)
            run = engine.create(load_task(task_path))
            result = engine.execute(run["id"])
            atomic_write(root / "result.json", canonical({
                "run_id": result["id"], "status": result["status"],
                "handoff": result["handoff"], "observed_tokens": result["observed_tokens"],
                "seconds": result["elapsed_seconds"], "error": result["error"],
                "fingerprint": result["config"]["fingerprint"],
                "native_state": str(native / "state"),
                "limitation": "One selected local FastAPI development smoke test, not a public benchmark or causal improvement estimate."}))
            shutil.copytree(native / "state" / "runs", root / "runs")
        finally:
            os.environ["PATH"] = old_path
            if old_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_home
    print(json.dumps({"status": result["status"], "tokens": result["observed_tokens"], "root": str(root)}))


if __name__ == "__main__":
    main()
