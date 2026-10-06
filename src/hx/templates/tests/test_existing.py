from backend.app import app
from fastapi.testclient import TestClient


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_create_and_read():
    client = TestClient(app)
    created = client.post("/tasks", json={"title": "existing behavior"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert client.get(f"/tasks/{task_id}").json()["title"] == "existing behavior"
