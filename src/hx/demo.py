from __future__ import annotations

import shutil
from pathlib import Path

from hx.acceptance import CHECKS
from hx.config import canonical
from hx.git import git
from hx.models import HXError, Task

REPORTS = {
    "missing-task": (
        "bug",
        "GET /tasks/{task_id} crashes for a missing task. Return HTTP 404 and preserve successful reads. Add a regression test.",
    ),
    "delete-task": (
        "bug",
        "DELETE /tasks/{task_id} reports success but leaves the task in the list. Delete the requested task and preserve other tasks. Add a regression test.",
    ),
    "empty-title": (
        "bug",
        "POST /tasks accepts empty or whitespace-only titles. Reject those titles with HTTP 422 while accepting nonempty titles. Add regression tests.",
    ),
    "filter-completed": (
        "feature",
        "Add optional completed=true/false filtering to GET /tasks. Omitted filtering must keep returning all tasks. Add tests for both filters.",
    ),
    "rename-task": (
        "feature",
        "Add PATCH /tasks/{task_id} to rename a task. Return the updated task, HTTP 404 for a missing task and HTTP 422 for empty or whitespace titles. Add tests.",
    ),
}


def initialize(directory: Path) -> list[Path]:
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise HXError(f"demo directory is not empty: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    repo = directory / "app"
    template = Path(__file__).parent / "templates"
    shutil.copytree(template, repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (repo / ".gitignore").write_text(
        "__pycache__/\n.pytest_cache/\n.coverage*\n*.sqlite3\n", "utf-8"
    )
    (repo / "README.md").write_text(
        "HX demo target. Five intentionally unfinished behaviors.\n", "utf-8"
    )
    git(repo, "init")
    git(repo, "config", "user.name", "HX Demo")
    git(repo, "config", "user.email", "hx@localhost")
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "Demo baseline")
    base = git(repo, "rev-parse", "HEAD")
    specs = directory / "tasks"
    specs.mkdir()
    paths = []
    for name, (kind, report) in REPORTS.items():
        task = Task(
            id=name, repo="../app", report=report, kind=kind, base_commit=base, acceptance=name
        )
        path = specs / (name + ".json")
        path.write_bytes(canonical(task.model_dump()))
        paths.append(path)
    return paths


def apply_fixture_fix(workspace: Path, name: str | None) -> None:
    if not name:
        raise HXError("fake adapter supports only the five demonstration tasks")
    path = workspace / "backend" / "app.py"
    source = path.read_text("utf-8")
    if name == "missing-task":
        source = source.replace(
            "        return dict(row)\n\n\n@app.post",
            "        if row is None:\n            raise HTTPException(status_code=404, detail='Task not found')\n        return dict(row)\n\n\n@app.post",
        )
    elif name == "delete-task":
        source = source.replace("(-task_id,)", "(task_id,)")
    elif name == "empty-title":
        source = source.replace(
            "def create_task(body: TaskInput):\n",
            "def create_task(body: TaskInput):\n    if not body.title.strip():\n        raise HTTPException(status_code=422, detail='Title must not be empty')\n",
        )
    elif name == "filter-completed":
        source = source.replace(
            "def list_tasks():", "def list_tasks(completed: bool | None = None):"
        )
        source = source.replace(
            '        return [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY id")]',
            '        if completed is not None:\n            return [dict(row) for row in db.execute("SELECT * FROM tasks WHERE completed=? ORDER BY id", (int(completed),))]\n        return [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY id")]',
        )
    elif name == "rename-task":
        source += """

@app.patch('/tasks/{task_id}')
def rename_task(task_id: int, body: TaskInput):
    if not body.title.strip():
        raise HTTPException(status_code=422, detail='Title must not be empty')
    with connection() as db:
        cursor = db.execute('UPDATE tasks SET title=? WHERE id=?', (body.title, task_id))
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail='Task not found')
        return dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())
"""
    path.write_text(source, "utf-8")
    # These fixture tests exercise real application behavior; the fake adapter is not an AI baseline.
    test = "from fastapi.testclient import TestClient\nfrom backend.app import app\n\ndef test_regression(tmp_path, monkeypatch):\n    monkeypatch.setenv('HX_DB', str(tmp_path / 'regression.sqlite3'))\n    client = TestClient(app)\n"
    test += "".join("    " + line + "\n" for line in CHECKS[name].strip().splitlines())
    (workspace / "tests" / "test_regression.py").write_text(test, "utf-8")
