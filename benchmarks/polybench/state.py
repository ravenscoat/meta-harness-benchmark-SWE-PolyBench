"""Native Linux SQLite with atomic, read-only console snapshots on Windows."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from hx.store import Store, atomic_write


class NativeStore(Store):
    def __init__(self, native: Path, public: Path):
        self.public = public.resolve()
        self.public.mkdir(parents=True, exist_ok=True)
        descriptor = self.public / "native-state.json"
        if not descriptor.exists():
            atomic_write(descriptor, json.dumps({"root": str(native.resolve())}).encode())
        super().__init__(native)
        self.publish()

    def run_dir(self, run_id):
        super().run_dir(run_id)  # Validate the ID using the core store.
        return self.public / "runs" / run_id

    @contextmanager
    def connection(self):
        with self._lock:
            with sqlite3.connect(self.db, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                yield conn
                changed = conn.total_changes
            if changed:
                self.publish()

    def publish(self):
        # Use a direct connection so snapshot reads cannot recursively publish.
        with sqlite3.connect(self.db, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            output = []
            for row in conn.execute("SELECT body FROM runs ORDER BY rowid DESC"):
                run = json.loads(row[0])
                steps = [dict(s) for s in conn.execute(
                    "SELECT id,status FROM steps WHERE run_id=? ORDER BY rowid", (run["id"],))]
                models = {e[0]: json.loads(e[1]).get("model", "") for e in conn.execute(
                    "SELECT step_id,data FROM events WHERE run_id=? AND type='worker.instantiated' ORDER BY seq", (run["id"],))}
                events = [dict(e) for e in conn.execute(
                    "SELECT seq,ts,type,step_id,data FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 8", (run["id"],))][::-1]
                output.append({"run": run, "steps": steps, "models": models, "events": events})
        # A Windows reader can deny replacement of an open file. Publish a new
        # immutable filename so a console read never blocks the SQLite writer.
        snapshot = self.public / f"console-snapshot.{time.time_ns()}.json"
        atomic_write(snapshot, json.dumps(output).encode())
        for old in sorted(self.public.glob("console-snapshot.*.json"))[:-10]:
            try:
                old.unlink()
            except OSError:
                pass  # A reader may still hold this obsolete snapshot open.


def trial_store(root, directory):
    public = directory / "state"
    descriptor = public / "native-state.json"
    if descriptor.exists():
        native = Path(json.loads(descriptor.read_text())["root"])
    else:
        storage = json.loads((root / "storage.json").read_text("utf-8-sig"))
        key = hashlib.sha256(str(directory.resolve()).encode()).hexdigest()
        native = Path(storage["execution_root"]) / "state" / key
    if (public / "state.sqlite3").exists():
        raise RuntimeError("legacy SQLite requires explicit evidence migration before retry")
    return NativeStore(native, public)
