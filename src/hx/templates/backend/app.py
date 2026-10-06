"""Small deliberately imperfect target for the five HX demonstration tasks."""

import os
import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="HX Notes")


class TaskInput(BaseModel):
    title: str


def connection():
    db = sqlite3.connect(os.environ.get("HX_DB", "notes.sqlite3"))
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0)"
    )
    db.commit()
    return db


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tasks", status_code=201)
def create_task(body: TaskInput):
    with connection() as db:
        cursor = db.execute("INSERT INTO tasks(title) VALUES (?)", (body.title,))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (cursor.lastrowid,)).fetchone()
        return dict(row)


@app.get("/tasks")
def list_tasks():
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY id")]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with connection() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row)


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    with connection() as db:
        cursor = db.execute("UPDATE tasks SET completed=1 WHERE id=?", (task_id,))
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"completed": True}


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    with connection() as db:
        db.execute("DELETE FROM tasks WHERE id=?", (-task_id,))
        return {"deleted": True}
