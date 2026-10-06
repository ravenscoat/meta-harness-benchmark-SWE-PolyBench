from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from hx.config import canonical
from hx.models import GateError, HXError


def now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


class Store:
    """SQLite owns ordered events and integrity metadata; workers never write here."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "state.sqlite3"
        self._lock = threading.RLock()
        with self.connection() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS steps (
                    run_id TEXT NOT NULL, id TEXT NOT NULL, cache_key TEXT NOT NULL,
                    status TEXT NOT NULL, artifact TEXT, sha256 TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (run_id, id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    ts TEXT NOT NULL, type TEXT NOT NULL, step_id TEXT, data TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        with self._lock, sqlite3.connect(self.db, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            yield conn

    def create(self, task: dict, config: dict, base: str) -> dict:
        run_id = "r-" + uuid.uuid4().hex[:16]
        run = {
            "id": run_id,
            "status": "pending",
            "created_at": now(),
            "updated_at": now(),
            "task": task,
            "config": config,
            "base_commit": base,
            "cancel_requested": False,
            "elapsed_seconds": 0.0,
            "observed_tokens": 0,
            "error": None,
            "handoff": None,
            "decision": None,
            "resume_count": 0,
        }
        self.run_dir(run_id).mkdir(parents=True)
        with self.connection() as conn:
            conn.execute("INSERT INTO runs VALUES (?, ?)", (run_id, canonical(run).decode()))
        self.event(run_id, "run.created", data={"base_commit": base})
        return run

    def run_dir(self, run_id: str) -> Path:
        # IDs must exist before they are accepted from the CLI/API; additionally forbid traversal.
        if not run_id.startswith("r-") or not run_id[2:].isalnum():
            raise HXError("invalid run ID")
        return self.root / "runs" / run_id

    def get(self, run_id: str) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HXError(f"run not found: {run_id}")
        return json.loads(row["body"])

    def update(self, run_id: str, **changes) -> dict:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise HXError(f"run not found: {run_id}")
            body = json.loads(row["body"])
            body.update(changes, updated_at=now())
            conn.execute("UPDATE runs SET body=? WHERE id=?", (canonical(body).decode(), run_id))
        return body

    def add_usage(self, run_id: str, tokens: int) -> None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            body = json.loads(
                conn.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()[0]
            )
            body["observed_tokens"] += tokens
            conn.execute("UPDATE runs SET body=? WHERE id=?", (canonical(body).decode(), run_id))

    def list(self) -> list[dict]:
        with self.connection() as conn:
            return [
                json.loads(row[0])
                for row in conn.execute("SELECT body FROM runs ORDER BY rowid DESC")
            ]

    def event(
        self, run_id: str, kind: str, step_id: str | None = None, data: dict | None = None
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO events (run_id, ts, type, step_id, data) VALUES (?, ?, ?, ?, ?)",
                (run_id, now(), kind, step_id, canonical(data or {}).decode()),
            )

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        self.get(run_id)
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)
            ).fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    def export_events(self, run_id: str) -> Path:
        path = self.run_dir(run_id) / "events.jsonl"
        atomic_write(path, b"".join(canonical(row) + b"\n" for row in self.events(run_id)))
        return path

    def steps(self, run_id: str) -> list[dict]:
        with self.connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM steps WHERE run_id=? ORDER BY rowid", (run_id,)
                )
            ]

    def cached(self, run_id: str, step_id: str, cache_key: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM steps WHERE run_id=? AND id=?", (run_id, step_id)
            ).fetchone()
        if not row or row["status"] != "completed" or row["cache_key"] != cache_key:
            return None
        path = self.run_dir(run_id) / row["artifact"]
        if not path.resolve().is_relative_to(self.run_dir(run_id).resolve()):
            raise GateError("artifact path escaped run directory")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise GateError("saved artifact is missing") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise GateError(f"artifact integrity check failed: {step_id}")
        return json.loads(data)

    def attempt(self, run_id: str, step_id: str, key: str) -> int:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM steps WHERE run_id=? AND id=?", (run_id, step_id)
            ).fetchone()
            number = row["attempts"] + 1 if row and row["cache_key"] == key else 1
            conn.execute(
                "INSERT OR REPLACE INTO steps VALUES (?, ?, ?, 'running', NULL, NULL, ?)",
                (run_id, step_id, key, number),
            )
        self.event(run_id, "step.started", step_id, {"attempt": number, "cache_key": key})
        return number

    def attempts(self, run_id: str, step_id: str, key: str) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT attempts, cache_key FROM steps WHERE run_id=? AND id=?", (run_id, step_id)
            ).fetchone()
        return row[0] if row and row[1] == key else 0

    def save(self, run_id: str, step_id: str, key: str, value: dict) -> None:
        relative = f"artifacts/{step_id}.json"
        data = canonical(value)
        atomic_write(self.run_dir(run_id) / relative, data)
        sha = hashlib.sha256(data).hexdigest()
        with self.connection() as conn:
            conn.execute(
                "UPDATE steps SET status='completed', artifact=?, sha256=? WHERE run_id=? AND id=? AND cache_key=?",
                (relative, sha, run_id, step_id, key),
            )
        self.event(run_id, "step.completed", step_id, {"artifact": relative, "sha256": sha})

    def failed(self, run_id: str, step_id: str, error: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE steps SET status='failed' WHERE run_id=? AND id=?", (run_id, step_id)
            )
        self.event(run_id, "step.failed", step_id, {"error": error})
