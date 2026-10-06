"""Fresh domain tasks for a fixed, prospective harness comparison."""

import json
import shutil
from pathlib import Path

from hx.challenge_suite import ASSETS
from hx.config import canonical, digest
from hx.git import git
from hx.models import HXError, Task
from hx.store import atomic_write

HERE = Path(__file__).parent
SPECS = {
    "seat-booking": "Reserve seats with POST /operation {key,show,seats}. Shows A and B each start with 5 remaining seats per owner. Seats must be a positive integer (not bool), show A/B, and a nonempty key of at most 80 characters. Reservation decrements remaining seats once and increments that show's version once. Insufficient capacity is 409 without any change. Concurrent reservations cannot oversell.",
    "stock-transfer": "Transfer stock with POST /operation {key,source,target,amount,source_version,target_version}. Sources/targets are distinct A/B. Each owner starts with A=10, B=0 at version1. Amount is a positive integer, versions positive integers (none may be bool). Missing stock or stale versions returns 409 without any state change. A valid transfer atomically debits/credits and increments both versions once. Concurrent writes using the same versions have exactly one winner.",
    "invoice-allocation": "Allocate integer cents with POST /operation {key,total,weights:[{id,weight}]}. Total is a nonnegative integer (not bool); 1..20 weights have unique nonempty string IDs and positive integer weights (not bool). Use largest remainder: floor each exact weighted share, then award remaining cents by descending integer remainder and ascending ID for ties. Return allocations sorted by ID with {id,cents}; their sum equals total. Save total in resource A and increment its version once. No floats may affect rounding.",
    "inbox-ack": "Acknowledge messages with POST /operation {key,messages:[{id,version}]}. Each owner has A and B unread (value0) at version1. The list has 1..20 unique IDs, each A/B, with positive integer versions (not bool). Validate the entire batch first. A stale version returns 409 and changes nothing. On success set each requested value to1 and increment its version once; unrequested messages are unchanged. Concurrent acknowledgements with the same version have one winner.",
}
COMMON = """All operations require X-Owner (missing/blank401), isolate owner state, and use durable owner/key replay. Exact replay returns the original successful JSON response without another write, even after other writes or a process restart. Reusing an owner/key for different content returns409. The same key is independent across owners. All validation failures return422 and perform no writes or replay inserts; retry with corrected content must work. Changes and replay records commit atomically. Preserve GET /health and GET /state (X-Owner, returns resources ordered by id with id,value,version).

Repair the React useOperationEditor({scope,send,initial}) in frontend/src/editor.jsx and keep the existing UI contract. scope is the current owner, initial is a stable JSON string. Return {draft,setDraft,result,error,pending,submit}. submit parses draft JSON and calls send(body,scope). Coalesce concurrent submits while the current scope request is pending. On success expose result and clear draft ONLY if it still equals the submitted draft; typing during await must survive. Parse/network errors set error and preserve draft. A scope change or unmount invalidates old work: old responses/rejections/finalizers must not alter current state, including switching A->B->A. Changing scope resets draft to initial and clears result/error/pending, allowing a new submission without waiting for old work. Handle StrictMode effect cleanup without breaking a mounted editor. Implement backend first, then verify the React UI. Add focused permitted tests; preserve protected existing tests and dependency manifests.
"""

BASE = '''import json, os, sqlite3
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()
DOMAIN = __DOMAIN__

def connection():
    c = sqlite3.connect(os.environ.get("HX_DB", "app.sqlite3"), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS resources(owner TEXT,id TEXT,value INTEGER,version INTEGER,PRIMARY KEY(owner,id))")
    c.execute("CREATE TABLE IF NOT EXISTS replay(owner TEXT,key TEXT,body TEXT,response TEXT,PRIMARY KEY(owner,key))")
    c.commit()
    return c

def owner(value):
    if not value or not value.strip(): raise HTTPException(401, "owner required")
    return value

def seed(c, who):
    values = [5,5] if DOMAIN=="seat-booking" else [10,0] if DOMAIN=="stock-transfer" else [0,0]
    for identifier,value in zip(["A","B"],values):
        c.execute("INSERT OR IGNORE INTO resources VALUES(?,?,?,1)",(who,identifier,value))

def integer(x, minimum=1):
    return type(x) is int and x>=minimum

def require(ok):
    if not ok: raise HTTPException(422, "invalid operation")

@app.get("/health")
def health(): return {"ok": True}

@app.get("/state")
def state(x_owner: str | None = Header(None)):
    who=owner(x_owner)
    with connection() as c:
        seed(c,who)
        return [dict(r) for r in c.execute("SELECT id,value,version FROM resources WHERE owner=? ORDER BY id",(who,))]

@app.post("/operation")
def operation(body: dict, x_owner: str | None = Header(None)):
    who=owner(x_owner)
    key=body.get("key")
    require(isinstance(key,str) and 0<len(key)<=80)
    encoded=json.dumps(body,sort_keys=True,separators=(",",":"))
    c=connection()
    try:
        c.execute("BEGIN IMMEDIATE")
        seed(c,who)
        old=c.execute("SELECT body,response FROM replay WHERE owner=? AND key=?",(who,key)).fetchone()
        if old:
            if old["body"]!=encoded: raise HTTPException(409,"key reused")
            return json.loads(old["response"])
        rows={r["id"]:dict(r) for r in c.execute("SELECT id,value,version FROM resources WHERE owner=?",(who,))}
__OPERATION__
        result={"resources":[dict(r) for r in c.execute("SELECT id,value,version FROM resources WHERE owner=? ORDER BY id",(who,))],**extra}
        c.execute("INSERT INTO replay VALUES(?,?,?,?)",(who,key,encoded,json.dumps(result)))
        c.commit()
        return result
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
'''

OPERATIONS = {
    "seat-booking": '''        show,seats=body.get("show"),body.get("seats")
        require(isinstance(show,str) and show in rows and integer(seats))
        if rows[show]["value"]<seats: raise HTTPException(409,"capacity")
        c.execute("UPDATE resources SET value=value-?,version=version+1 WHERE owner=? AND id=?",(seats,who,show))
        extra={}
''',
    "stock-transfer": '''        source,target,amount=body.get("source"),body.get("target"),body.get("amount")
        sv,tv=body.get("source_version"),body.get("target_version")
        require(isinstance(source,str) and isinstance(target,str) and source in rows and target in rows and source!=target and integer(amount) and integer(sv) and integer(tv))
        if rows[source]["value"]<amount or rows[source]["version"]!=sv or rows[target]["version"]!=tv: raise HTTPException(409,"stock/version")
        c.execute("UPDATE resources SET value=value-?,version=version+1 WHERE owner=? AND id=?",(amount,who,source))
        c.execute("UPDATE resources SET value=value+?,version=version+1 WHERE owner=? AND id=?",(amount,who,target))
        extra={}
''',
    "invoice-allocation": '''        total,weights=body.get("total"),body.get("weights")
        require(integer(total,0) and isinstance(weights,list) and 1<=len(weights)<=20)
        require(all(isinstance(w,dict) and isinstance(w.get("id"),str) and w["id"] and integer(w.get("weight")) for w in weights))
        require(len({w["id"] for w in weights})==len(weights))
        denominator=sum(w["weight"] for w in weights)
        parts=[{"id":w["id"],"cents":total*w["weight"]//denominator,"remainder":total*w["weight"]%denominator} for w in weights]
        remaining=total-sum(p["cents"] for p in parts)
        for p in sorted(parts,key=lambda p:(-p["remainder"],p["id"]))[:remaining]: p["cents"]+=1
        allocations=[{"id":p["id"],"cents":p["cents"]} for p in sorted(parts,key=lambda p:p["id"])]
        c.execute("UPDATE resources SET value=?,version=version+1 WHERE owner=? AND id='A'",(total,who))
        extra={"allocations":allocations}
''',
    "inbox-ack": '''        messages=body.get("messages")
        require(isinstance(messages,list) and 1<=len(messages)<=20)
        require(all(isinstance(m,dict) and isinstance(m.get("id"),str) and m["id"] in rows and integer(m.get("version")) for m in messages))
        require(len({m["id"] for m in messages})==len(messages))
        if any(rows[m["id"]]["version"]!=m["version"] for m in messages): raise HTTPException(409,"stale message")
        for m in messages:
            c.execute("UPDATE resources SET value=1,version=version+1 WHERE owner=? AND id=?",(who,m["id"]))
        extra={}
''',
}


def backend(domain, reference=False):
    program = BASE.replace("__DOMAIN__", repr(domain)).replace("__OPERATION__", OPERATIONS[domain].rstrip())
    if reference:
        return program
    # Plausible implementations with domain-specific defects plus broken replay.
    program = program.replace('return type(x) is int and x>=minimum', 'return isinstance(x,int) and x>=minimum')
    program = program.replace('return json.loads(old["response"])', 'return {"resources": [dict(r) for r in c.execute("SELECT id,value,version FROM resources WHERE owner=? ORDER BY id",(who,))]}')
    if domain == "seat-booking":
        program = program.replace('if rows[show]["value"]<seats:', 'if rows[show]["value"]<0:')
    elif domain == "stock-transfer":
        program = program.replace(' or rows[target]["version"]!=tv', '')
    elif domain == "invoice-allocation":
        program = program.replace('(-p["remainder"],p["id"])', '(-p["remainder"], -ord(p["id"][0]))')
    else:
        program = program.replace('if any(rows[m["id"]]["version"]!=m["version"] for m in messages)', 'if all(rows[m["id"]]["version"]!=m["version"] for m in messages)')
    return program


def build(root):
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise HXError("fresh collection directory must be empty")
    cases = []
    for domain, spec in SPECS.items():
        repo = root / "repos" / domain
        (repo / "backend").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "backend/__init__.py").write_text("")
        (repo / "backend/app.py").write_text(backend(domain), encoding="utf-8")
        (repo / "tests/test_existing.py").write_text('from fastapi.testclient import TestClient\nfrom backend.app import app\n\ndef test_health():\n    assert TestClient(app).get("/health").json()=={"ok":True}\n', encoding="utf-8")
        shutil.copytree(ASSETS / "fullstack", repo / "frontend", ignore=shutil.ignore_patterns("node_modules", "dist", "src"))
        src = repo / "frontend/src"
        src.mkdir()
        (src / "editor.jsx").write_bytes((HERE / "editor_seed.jsx").read_bytes())
        (src / "main.jsx").write_bytes((HERE / "main.jsx").read_bytes())
        (src / "existing.test.jsx").write_bytes((HERE / "existing.test.jsx").read_bytes())
        (repo / ".gitignore").write_text('__pycache__/\n.pytest_cache/\n.coverage*\n*.sqlite3\nnode_modules/\ndist/\n', encoding="utf-8")
        report = spec + "\n\n" + COMMON
        (repo / "README.md").write_text(f"# {domain}\n\n{report}\n\nBackend: backend/app.py. React: frontend/src/editor.jsx. HX_DB configures SQLite. Python dependencies and locked npm packages are installed offline. UI controls: Owner select, JSON operation textbox, Submit operation button, pending status, error alert and result output. Do not alter those accessible labels.\n", encoding="utf-8")
        git(repo, "init")
        git(repo, "config", "user.name", "HX Benchmark")
        git(repo, "config", "user.email", "hx@localhost")
        git(repo, "add", "--all")
        git(repo, "commit", "--quiet", "-m", "Fresh prospective task seed")
        task = Task(id=domain, repo=str(repo), report=report, frontend=True,
                    base_commit=git(repo, "rev-parse", "HEAD"),
                    allowed_paths=["backend/**", "tests/**", "frontend/src/**"],
                    protected_paths=["tests/test_existing.py", "frontend/src/existing.test.jsx", "frontend/src/main.jsx", "frontend/package.json", "frontend/package-lock.json"])
        path = root / "tasks" / (domain + ".json")
        atomic_write(path, canonical(task.model_dump()))
        cases.append({"id": domain, "task": str(path), "task_sha256": digest(task.model_dump()),
                      "split": "heldout", "groups": ["backend", "browser"]})
    manifest = {"version": "hx-fresh-domains-v1", "cases": cases,
                "limitations": "AI-authored synthetic domain repos share scaffolding and an editor contract; not independent human ground truth or unrelated real-world projects."}
    atomic_write(root / "manifest.json", canonical(manifest))
    return manifest


if __name__ == "__main__":
    import sys

    print(json.dumps(build(Path(sys.argv[1])), indent=2))
