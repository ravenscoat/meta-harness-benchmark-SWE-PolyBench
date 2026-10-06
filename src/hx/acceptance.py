"""Trusted demo evaluator; diagnostic output is not exposed in worker context.

Local filesystem isolation is NOT a secrecy boundary. Use OS/container isolation
before treating these checks as a hidden adversarial benchmark.
"""

CHECKS = {
    "missing-task": """
r = client.get('/tasks/999999')
assert r.status_code == 404
r = client.post('/tasks', json={'title': 'valid'})
assert client.get('/tasks/' + str(r.json()['id'])).status_code == 200
""",
    "delete-task": """
r = client.post('/tasks', json={'title': 'delete me'})
task_id = r.json()['id']
assert client.delete('/tasks/' + str(task_id)).status_code in (200, 204)
assert task_id not in [x['id'] for x in client.get('/tasks').json()]
""",
    "empty-title": """
for title in ['', ' ', '\\t\\n']:
    assert client.post('/tasks', json={'title': title}).status_code == 422
assert client.post('/tasks', json={'title': 'valid'}).status_code == 201
""",
    "filter-completed": """
a = client.post('/tasks', json={'title': 'open'}).json()['id']
b = client.post('/tasks', json={'title': 'done'}).json()['id']
assert client.post('/tasks/' + str(b) + '/complete').status_code == 200
assert [x['id'] for x in client.get('/tasks?completed=true').json()] == [b]
assert [x['id'] for x in client.get('/tasks?completed=false').json()] == [a]
assert len(client.get('/tasks').json()) == 2
""",
    "rename-task": """
a = client.post('/tasks', json={'title': 'before'}).json()['id']
r = client.patch('/tasks/' + str(a), json={'title': 'after'})
assert r.status_code == 200
assert client.get('/tasks/' + str(a)).json()['title'] == 'after'
assert client.patch('/tasks/999999', json={'title': 'after'}).status_code == 404
assert client.patch('/tasks/' + str(a), json={'title': ' '}).status_code == 422
""",
}


def program(name: str) -> str:
    return (
        "from fastapi.testclient import TestClient\nfrom backend.app import app\nclient = TestClient(app)\n"
        + CHECKS[name]
    )
