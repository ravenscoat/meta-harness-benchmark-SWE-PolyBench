"""Read-only Codex account usage; no credit redemption or model requests."""
import json
import os
import selectors
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def compact_usage(response):
    limits = (response.get("rateLimitsByLimitId") or {}).get("codex") or response.get("rateLimits")
    if not isinstance(limits, dict):
        raise RuntimeError("Account usage unavailable; no model trial started")
    windows = {}
    for name in ("primary", "secondary"):
        value = limits.get(name)
        if not isinstance(value, dict) or not isinstance(value.get("usedPercent"), (int, float)):
            raise RuntimeError("Account usage window unavailable; no model trial started")
        windows[name] = {key: value.get(key) for key in ("usedPercent", "resetsAt")}
    return {"checked": time.time(), "ordinary_allowed": response.get("ordinaryUsageAllowed") is True,
            **windows}


def can_start(usage):
    return (usage["ordinary_allowed"] and usage["primary"]["usedPercent"] < 80
            and usage["secondary"]["usedPercent"] < 90)


def account_usage(binary: Path, auth: Path, timeout=30):
    with tempfile.TemporaryDirectory(prefix="hx-account-read-") as home:
        target = Path(home) / "auth.json"
        shutil.copyfile(auth, target)
        target.chmod(0o600)
        env = {**os.environ, "CODEX_HOME": home}
        proc = subprocess.Popen([str(binary), "--no-daemon", "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        buffer = b""
        deadline = time.monotonic() + timeout

        def send(message):
            proc.stdin.write((json.dumps(message) + "\n").encode())
            proc.stdin.flush()

        def receive(wanted):
            nonlocal buffer
            while time.monotonic() < deadline:
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    message = json.loads(line)
                    if message.get("id") == wanted:
                        if "error" in message:
                            raise RuntimeError("Read-only account request failed; no model trial started")
                        return message["result"]
                if not selector.select(max(0, deadline - time.monotonic())):
                    break
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffer += chunk
            raise RuntimeError("Account usage request timed out; no model trial started")

        try:
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "hx-overnight", "version": "0.1"}}})
            receive(1)
            send({"method": "initialized"})
            send({"id": 2, "method": "account/rateLimits/read", "params": {
                "excludeResetCreditDetails": True, "supportsLunaReserve": False}})
            return compact_usage(receive(2))
        finally:
            selector.close()
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    from benchmarks.polybench.runner import AUTH, BINARY
    print(json.dumps(account_usage(BINARY, AUTH)))
