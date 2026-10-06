"""Evaluator only: public requirements, independent scenarios, fresh databases."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from backend.app import app
from fastapi.testclient import TestClient

DOMAIN = sys.argv[1]
client = TestClient(app)


def body(key="one"):
    value = {"key": key}
    value.update({
        "seat-booking": {"show": "A", "seats": 2},
        "stock-transfer": {"source": "A", "target": "B", "amount": 3,
                           "source_version": 1, "target_version": 1},
        "invoice-allocation": {"total": 2, "weights": [{"id": "z", "weight": 1},
                                                       {"id": "a", "weight": 1},
                                                       {"id": "m", "weight": 1}]},
        "inbox-ack": {"messages": [{"id": "A", "version": 1}, {"id": "B", "version": 1}]},
    }[DOMAIN])
    return value


def post(value, owner="alpha"):
    return client.post("/operation", json=value, headers={"X-Owner": owner})


def state(owner="alpha"):
    response = client.get("/state", headers={"X-Owner": owner})
    assert response.status_code == 200
    return response.json()


assert client.post("/operation", json=body()).status_code == 401
assert client.get("/state").status_code == 401
initial = state()
invalid = body("correctable")
if DOMAIN == "seat-booking":
    invalid["seats"] = True
elif DOMAIN == "stock-transfer":
    invalid["target_version"] = True
elif DOMAIN == "invoice-allocation":
    invalid["weights"][1]["weight"] = True
else:
    invalid["messages"][1]["version"] = True
assert post(invalid).status_code == 422, "boolean accepted as integer"
assert state() == initial, "invalid request changed state"
assert post(body("correctable")).status_code == 200, "invalid request consumed replay key"

first = post(body("one"), "replay")
assert first.status_code == 200
if DOMAIN == "invoice-allocation":
    assert first.json()["allocations"] == [{"id": "a", "cents": 1}, {"id": "m", "cents": 1}, {"id": "z", "cents": 0}]
different = body("two")
if DOMAIN == "stock-transfer":
    different.update(source_version=2, target_version=2)
elif DOMAIN == "inbox-ack":
    different["messages"] = [{"id": "A", "version": 2}]
assert post(different, "replay").status_code == 200
before = state("replay")
assert post(body("one"), "replay").json() == first.json(), "replay was not immutable"
assert state("replay") == before, "replay wrote again"
# The same database is opened in a genuinely new Python process.
program = "from fastapi.testclient import TestClient;from backend.app import app;import json;print(json.dumps(TestClient(app).post('/operation',json=" + repr(body("one")) + ",headers={'X-Owner':'replay'}).json()))"
restarted = subprocess.check_output([sys.executable, "-c", program], env=os.environ.copy(), text=True)
assert json.loads(restarted) == first.json(), "restart replay changed"
changed = body("one")
changed["extra"] = "different request"
assert post(changed, "replay").status_code == 409
assert post(body("one"), "other-owner").status_code == 200
assert state("alpha") != state("untouched"), "owner changes absent"
assert state("untouched") == initial, "owner state leaked"

if DOMAIN == "seat-booking":
    too_many = body("oversell")
    too_many["seats"] = 6
    before = state("capacity")
    assert post(too_many, "capacity").status_code == 409
    assert state("capacity") == before
elif DOMAIN == "stock-transfer":
    stale = body("stale")
    stale["target_version"] = 2
    before = state("atomic")
    assert post(stale, "atomic").status_code == 409
    assert state("atomic") == before, "partial transfer committed"
elif DOMAIN == "invoice-allocation":
    invalid = body("duplicate")
    invalid["weights"][1]["id"] = invalid["weights"][0]["id"]
    before = state("atomic")
    assert post(invalid, "atomic").status_code == 422
    assert state("atomic") == before
    huge = body("large")
    huge["total"] = 10**18 + 1
    value = post(huge, "large")
    assert value.status_code == 200
    assert sum(p["cents"] for p in value.json()["allocations"]) == huge["total"]
else:
    invalid = body("mixed")
    invalid["messages"][1]["version"] = 99
    before = state("atomic")
    assert post(invalid, "atomic").status_code == 409
    assert state("atomic") == before, "partial acknowledgement committed"

if DOMAIN != "invoice-allocation":
    def attempt(number):
        request = body(f"concurrent-{number}")
        if DOMAIN == "seat-booking":
            request["seats"] = 3
        return post(request, "concurrent").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(attempt, [1, 2]))
    assert sorted(codes) == [200, 409], f"concurrent writers: {codes}"
    rows = state("concurrent")
    if DOMAIN == "seat-booking":
        assert rows[0]["value"] == 2
    elif DOMAIN == "stock-transfer":
        assert [r["value"] for r in rows] == [7, 3]
    else:
        assert [r["version"] for r in rows] == [2, 2]
print("backend contract, durable replay, atomicity and ownership passed")
