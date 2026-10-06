import time

from fastapi.testclient import TestClient

from hx.adapters import FakeAdapter
from hx.api import create_app
from hx.models import Settings


def test_authenticated_api_runs_and_approves_exact_candidate(project, tmp_path):
    app = create_app(
        tmp_path / "api", Settings(adapter="fake", max_attempts=1, max_revisions=0), FakeAdapter()
    )
    token = app.state.token_path.read_text("utf-8")
    headers = {"Authorization": "Bearer " + token}
    with TestClient(app) as client:
        assert "Changes backed by evidence" in client.get("/").text
        assert client.get("/app.js").status_code == 200
        assert client.get("/style.css").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/runs").status_code == 401
        assert (
            client.post("/runs", json={"task": project["missing-task"].model_dump()}).status_code
            == 401
        )
        response = client.post(
            "/runs", headers=headers, json={"task": project["missing-task"].model_dump()}
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        until = time.monotonic() + 60
        while time.monotonic() < until:
            run = client.get(f"/runs/{run_id}", headers=headers).json()
            if run["status"] not in {"pending", "running"}:
                break
            time.sleep(0.1)
        assert run["status"] == "ready_for_approval", run["error"]
        assert "HTTPException" in client.get(f"/runs/{run_id}/diff", headers=headers).text
        assert client.get(f"/runs/{run_id}/events", headers=headers).json()
        wrong = client.post(
            f"/runs/{run_id}/approve", headers=headers, json={"candidate_commit": "wrong"}
        )
        assert wrong.status_code == 409
        good = client.post(
            f"/runs/{run_id}/approve",
            headers=headers,
            json={"candidate_commit": run["handoff"]["candidate_commit"]},
        )
        assert good.status_code == 200
        assert good.json()["status"] == "approved"
        assert client.get("/runs/../../escape", headers=headers).status_code in {404, 405}
