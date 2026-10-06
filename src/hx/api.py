from __future__ import annotations

import hmac
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from hx.config import load_settings, load_task
from hx.engine import Engine
from hx.git import git
from hx.models import Candidate, Contract, HXError, Settings, Task
from hx.store import Store, atomic_write


class Submit(Contract):
    task: Task


class Decision(Contract):
    candidate_commit: str
    reason: str = Field(default="", max_length=4000)


def create_app(
    state_dir: Path | None = None, settings: Settings | None = None, adapter=None
) -> FastAPI:
    store = Store(state_dir or Path(".hx"))
    if settings is None:
        config = Path("hx.toml")
        settings = load_settings(config if config.exists() else None)
    token_path = store.root / "api-token.txt"
    if not token_path.exists():
        atomic_write(token_path, secrets.token_urlsafe(32).encode())
        try:
            token_path.chmod(0o600)
        except OSError:
            pass
    token = token_path.read_text("utf-8").strip()
    engine = Engine(store, settings, adapter)
    guard = threading.Lock()
    jobs = {}
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hx-workflow")

    @asynccontextmanager
    async def lifespan(_app):
        yield
        with guard:
            for run_id, future in jobs.items():
                if not future.done():
                    store.update(run_id, cancel_requested=True)
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="HX Harness", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.engine = engine
    app.state.token_path = token_path

    def authenticated(authorization: str | None = Header(default=None)):
        supplied = authorization.removeprefix("Bearer ") if authorization else ""
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(status_code=401, detail="Bearer token required")

    def get_run(run_id: str) -> dict:
        try:
            return store.get(run_id)
        except HXError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def enqueue(run_id: str, resume: bool = False):
        with guard:
            if any(not future.done() and key == run_id for key, future in jobs.items()):
                raise HTTPException(status_code=409, detail="run already queued or executing")
            if sum(not future.done() for future in jobs.values()) >= 8:
                raise HTTPException(status_code=429, detail="local run queue is full")

            def work():
                try:
                    engine.execute(run_id, resume=resume)
                except Exception as exc:
                    # A rejected dispatch must not overwrite another process's active run.
                    current = store.get(run_id)
                    if current["status"] not in {
                        "running",
                        "ready_for_approval",
                        "needs_attention",
                        "approved",
                        "denied",
                    }:
                        store.update(run_id, status="failed", error=str(exc))
                    store.event(run_id, "dispatch.rejected", data={"error": str(exc)})

            jobs[run_id] = executor.submit(work)

    auth = [Depends(authenticated)]

    @app.get("/health")
    def health():
        return {"status": "ok", "adapter": settings.adapter}

    @app.get("/runs", dependencies=auth)
    def runs():
        return store.list()

    @app.get("/demo/tasks", dependencies=auth)
    def demo_tasks():
        return [
            load_task(path).model_dump()
            for path in sorted((store.root / "demo" / "tasks").glob("*.json"))
        ]

    @app.post("/runs", status_code=202, dependencies=auth)
    def submit(body: Submit):
        try:
            run = engine.create(body.task.resolved(Path.cwd()))
        except (HXError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        enqueue(run["id"])
        return {"run_id": run["id"], "status": "pending"}

    @app.get("/runs/{run_id}", dependencies=auth)
    def status(run_id: str):
        return {**get_run(run_id), "steps": store.steps(run_id)}

    @app.get("/runs/{run_id}/events", dependencies=auth)
    def events(run_id: str, after: int = 0):
        get_run(run_id)
        return store.events(run_id, after)

    @app.get("/runs/{run_id}/diff", response_class=PlainTextResponse, dependencies=auth)
    def diff(run_id: str):
        run = get_run(run_id)
        candidates = [
            step
            for step in store.steps(run_id)
            if step["status"] == "completed"
            and (step["id"] == "implement" or step["id"].startswith("revise_"))
        ]
        if not candidates:
            raise HTTPException(status_code=409, detail="no candidate yet")
        step = candidates[-1]
        try:
            candidate = Candidate.model_validate(
                store.cached(run_id, step["id"], step["cache_key"])
            )
            return git(
                Path(candidate.workspace),
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                run["base_commit"],
                candidate.candidate_commit,
            )
        except (HXError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/runs/{run_id}/artifacts/{step_id}", dependencies=auth)
    def artifact(run_id: str, step_id: str):
        get_run(run_id)
        row = next((row for row in store.steps(run_id) if row["id"] == step_id), None)
        if not row or row["status"] != "completed":
            raise HTTPException(status_code=404, detail="completed artifact not found")
        try:
            return store.cached(run_id, step_id, row["cache_key"])
        except HXError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/runs/{run_id}/cancel", status_code=202, dependencies=auth)
    def cancel(run_id: str):
        run = get_run(run_id)
        if run["status"] not in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="run is not pending or running")
        store.update(run_id, cancel_requested=True)
        store.event(run_id, "cancel.requested")
        return {"run_id": run_id, "cancel_requested": True}

    @app.post("/runs/{run_id}/resume", status_code=202, dependencies=auth)
    def resume(run_id: str):
        run = get_run(run_id)
        if run["status"] not in {"failed", "cancelled", "running"}:
            raise HTTPException(status_code=409, detail="run cannot be resumed in this state")
        enqueue(run_id, resume=True)
        return {"run_id": run_id, "status": "resume_queued"}

    def decide(run_id: str, body: Decision, approve: bool):
        get_run(run_id)
        try:
            return engine.decision(run_id, body.candidate_commit, approve, body.reason)
        except (HXError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/runs/{run_id}/approve", dependencies=auth)
    def approve(run_id: str, body: Decision):
        return decide(run_id, body, True)

    @app.post("/runs/{run_id}/deny", dependencies=auth)
    def deny(run_id: str, body: Decision):
        return decide(run_id, body, False)

    # Serve the first-party dashboard last, so API routes retain precedence.
    app.mount(
        "/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="dashboard"
    )
    return app
