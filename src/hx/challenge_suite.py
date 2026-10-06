from __future__ import annotations

import shutil
from pathlib import Path

from hx.config import canonical, digest
from hx.git import git
from hx.models import HXError, Task

ASSETS = Path(__file__).resolve().parents[2] / "benchmarks"
VERSION = "hx-fullstack-hard-v1"

# Original tasks, informed by public evaluation methodology. No upstream tasks copied.
CASES = {
    "atomic-create": (
        "search",
        ["idempotency"],
        "Concurrent retries create duplicate cards. Make POST /items idempotent per tenant and Idempotency-Key, including simultaneous identical retries. Replay the original 201 body without duplicate audit events; different payload reuse must return 409. Other tenants may reuse the same key. Writes and replay records must be atomic and survive restarts.",
    ),
    "tenant-version": (
        "search",
        ["tenant", "version"],
        "Cross-tenant reads and stale edits corrupt cards. Every read and mutation must require X-Tenant and scope by it, returning 404 for another tenant's card. PATCH requires If-Match (428 absent, 412 stale), atomically compares and increments version once, returns ETag, and creates exactly one audit event. Simultaneous writers using one version must have exactly one winner.",
    ),
    "cursor-ties": (
        "search",
        ["cursor"],
        "Pagination skips cards when timestamps tie. GET /items must return unarchived tenant-scoped cards ordered by (updated DESC, id DESC), limit 1..20, with opaque keyset next_cursor or null. Bind cursors to tenant and exact q, reject malformed/cross-scope cursors with 422, and apply case-insensitive literal substring filtering. New head inserts between page requests must not repeat previous cards.",
    ),
    "search-race": (
        "search",
        ["search"],
        "React useSearch shows stale tenant data and stale errors after rapid search changes. Keep the exported API {items,error,loading}; latest query AND tenant own the result. Clear old items at request start, ignore obsolete resolutions/rejections and unmounted results, handle sync throws, and recover after a failed request. Preserve fetcher injection and hook signatures.",
    ),
    "optimistic-race": (
        "search",
        ["board"],
        "React useOptimisticBoard loses unrelated successful edits on a failed save and lets older saves overwrite newer ones. Keep {items,rename}. Update immediately; isolate pending operations by item and generation; rollback only the failed current operation; stale success/failure cannot replace a newer title. Reconcile incoming initial items without clobbering pending edits. Propagate rejected saves to callers.",
    ),
    "workspace-reliability": (
        "search",
        [
            "idempotency",
            "tenant",
            "version",
            "cursor",
            "archive",
            "patch",
            "search",
            "board",
            "editor",
        ],
        "Stabilize this full-stack workspace for concurrent multi-tenant use. Backend: atomic per-tenant idempotent creates (201 replay,409 payload conflict), mandatory tenant isolation, CAS PATCH (428 missing If-Match,412 stale), nonempty patches with explicit null forbidden, all-or-nothing deduplicated bulk archive, and stable scoped keyset pagination with literal case-insensitive q. React: latest query/tenant owns search; per-item generation-aware optimistic rollback; editor save completion must preserve typing and not alter a subsequently opened card. Keep routes, response shapes and hook signatures. Add adversarial regression tests, not only happy paths.",
    ),
    "replay-isolation": (
        "heldout",
        ["idempotency", "tenant"],
        "Fix retry and ownership isolation for POST/GET/PATCH. Missing or blank X-Tenant is 401; another tenant's card is indistinguishable from missing (404). Concurrent idempotency retries with the same tenant/key/body return identical 201 bodies and one insert/audit; mismatched bodies return409. Reuse across tenants is independent. Persist replay behavior across fresh client instances.",
    ),
    "archive-transaction": (
        "heldout",
        ["archive"],
        "Bulk archive partially commits when a late ID is invalid. POST /archive {ids:[...]} must atomically validate ownership of every ID, reject empty/>100 unique IDs with422, reject missing/foreign IDs with404, deduplicate preserving first occurrence order, and return those IDs. Each newly archived card increments version once and emits one audit event; already archived cards are no-ops. Invalid batches change neither cards nor audit. Concurrent repeated batches must not double-apply.",
    ),
    "patch-semantics": (
        "heldout",
        ["patch", "version"],
        "PATCH conflates omitted, null and false and accepts lost updates. Require tenant and If-Match; absent precondition428, stale412 with no mutation/audit. Empty or explicitly null fields422. Omitted fields preserve existing values, archived:false unarchives, blank/over120-character title422. Accepted patches increment version once, expose ETag, and survive restart. Atomic CAS must prevent simultaneous writes with identical preconditions.",
    ),
    "editor-session": (
        "heldout",
        ["editor"],
        "React useEditor completes old saves into the wrong editing session and erases text typed while saving. Keep {draft,error,saving,open,edit,save}. Opening another card resets error/saving; old successes/errors must not alter it. Same-session save responses update server version while preserving newer typed title. Current errors preserve draft and allow retry. Unmounted completions must be ignored. Preserve hook arguments.",
    ),
    "refresh-race": (
        "heldout",
        ["search", "board"],
        "Fix React search and board reconciliation under out-of-order network activity. Tenant/query changes immediately clear prior results and stale resolutions/errors cannot replace current state. Independent optimistic edits must survive another item's failed mutation and server refreshes while pending; old mutations cannot overwrite newer ones on the same item. Keep all exported signatures and propagate rename errors.",
    ),
    "workspace-integrity": (
        "heldout",
        [
            "idempotency",
            "tenant",
            "version",
            "cursor",
            "archive",
            "patch",
            "search",
            "board",
            "editor",
        ],
        "Complete the full-stack integrity repair. Preserve existing public API and React hook exports. Enforce mandatory tenant ownership; atomic per-tenant durable idempotency with payload conflict detection; version preconditions/ETags; omitted/null/false PATCH semantics; transactional deduplicated archive including no-op repeats; deterministic scoped keyset pagination and literal case-insensitive filtering. React must correctly handle obsolete search responses, independent and repeated optimistic mutations, refresh during pending edits, editing during save, opening another card during save, rejection/retry and unmount. Add regression tests covering concurrency and delayed promise ordering.",
    ),
}

BACKEND_FAULTS = {
    "idempotency": [
        ("if idempotency_key:\n            row =", "if False:\n            row ="),
        ("PRIMARY KEY(tenant,key)", "PRIMARY KEY(tenant,key)"),
        (
            "db.execute('INSERT INTO requests VALUES(?,?,?,?)'",
            "db.execute('INSERT OR REPLACE INTO requests VALUES(?,?,?,?)'",
        ),
    ],
    "tenant": [
        (
            "WHERE tenant=? AND id=?', (tenant, item_id)",
            "WHERE id=? OR tenant=?', (item_id, tenant)",
        )
    ],
    "version": [
        ("if if_match is None:", "if False:"),
        ("if if_match != str(current['version']):", "if False:"),
    ],
    "patch": [
        (
            "if not supplied or (('title' in supplied and body.title is None) or ('archived' in supplied and body.archived is None)):",
            "if False:",
        ),
        ("if 'title' in supplied else current['title']", "if body.title else current['title']"),
        (
            "int(body.archived) if 'archived' in supplied else current['archived']",
            "int(body.archived) if body.archived else current['archived']",
        ),
    ],
    "archive": [
        ("ids = list(dict.fromkeys(body.ids))", "ids = body.ids"),
        ("rows = [lookup(db,tenant,item_id) for item_id in ids]", "rows = []"),
        ("for row in rows:", "for item_id in ids:\n            row = lookup(db,tenant,item_id)"),
        ("if not row['archived']:", "if True:"),
        ("return {'ids':ids}", "    db.commit()\n        return {'ids':ids}"),
    ],
    "cursor": [
        ("ORDER BY updated DESC,id DESC", "ORDER BY updated DESC"),
        ("(r['updated'],r['id']) < anchor", "r['updated'] < anchor[0]"),
        ("payload['tenant'] != tenant or payload['q'] != q or", "False or"),
    ],
}
FRONTEND_FAULTS = {
    "search": [
        ("if (current) setState", "if (true) setState"),
        ("[query, tenant, fetcher]", "[query, fetcher]"),
    ],
    "board": [
        ("if (pending.current.get(id) === token)", "if (true)"),
        ("setItems(current => current.map(i => i.id === id ? before : i));", "setItems(initial);"),
        ("pending.current.has(item.id)", "false"),
    ],
    "editor": [
        ("live.current && session.current === startedSession", "live.current"),
        (
            "revision.current === startedRevision ? {...result} : {...current, version:result.version}",
            "({...result})",
        ),
    ],
}


def materialize(directory: Path) -> Path:
    directory = directory.resolve()
    if directory.exists() and any(directory.iterdir()):
        raise HXError("challenge directory must be empty")
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": VERSION,
        "cases": [],
        "source": "original synthetic tasks; not SWE-bench/Terminal-Bench scores",
    }
    for name, (split, groups, report) in CASES.items():
        repo = directory / "repos" / name
        (repo / "backend").mkdir(parents=True)
        (repo / "tests").mkdir()
        shutil.copytree(
            ASSETS / "fullstack",
            repo / "frontend",
            ignore=shutil.ignore_patterns("node_modules", "dist"),
        )
        (repo / ".gitignore").write_text(
            "__pycache__/\n.pytest_cache/\n.coverage*\n*.sqlite3\nnode_modules/\ndist/\n", "utf-8"
        )
        (repo / "backend" / "__init__.py").write_text("", "utf-8")
        backend = (ASSETS / "backend_reference.py").read_text("utf-8")
        frontend = (repo / "frontend/src/hooks.jsx").read_text("utf-8")
        for group in groups:
            for old, new in BACKEND_FAULTS.get(group, []):
                if old not in backend:
                    raise HXError(f"fault injection anchor missing: {group}")
                backend = backend.replace(old, new)
            for old, new in FRONTEND_FAULTS.get(group, []):
                if old not in frontend:
                    raise HXError(f"fault injection anchor missing: {group}")
                frontend = frontend.replace(old, new)
        (repo / "backend/app.py").write_text(backend, "utf-8")
        (repo / "frontend/src/hooks.jsx").write_text(frontend, "utf-8")
        (repo / "tests/test_existing.py").write_text(
            "from fastapi.testclient import TestClient\nfrom backend.app import app\n\ndef test_health():\n    assert TestClient(app).get('/health').json() == {'ok': True}\n",
            "utf-8",
        )
        (repo / "README.md").write_text(
            "Run Python tests using the supplied python_executable. Frontend: npm test -- --maxWorkers=1; npm run build. Node dependencies are preinstalled offline by HX. API: X-Tenant header, items contain id/tenant/title/version/updated/archived; GET /items returns {items,next_cursor}. React hooks in frontend/src/hooks.jsx. Preserve exports and response shapes. Database configured through HX_DB.\n",
            "utf-8",
        )
        git(repo, "init")
        git(repo, "config", "user.name", "HX Benchmark")
        git(repo, "config", "user.email", "hx@localhost")
        git(repo, "add", "--all")
        git(repo, "commit", "--quiet", "-m", VERSION + ": " + name)
        task = Task(
            id=name,
            repo=str(repo),
            report=report,
            base_commit=git(repo, "rev-parse", "HEAD"),
            allowed_paths=["backend/**", "tests/**", "frontend/src/**"],
            protected_paths=["tests/test_existing.py", "frontend/src/existing.test.jsx"],
            acceptance=None,
            frontend=True,
        )
        path = directory / "tasks" / split / (name + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(task.model_dump()))
        manifest["cases"].append(
            {
                "id": name,
                "split": split,
                "groups": groups,
                "task": str(path),
                "base_commit": task.base_commit,
                "task_sha256": digest(task.model_dump()),
            }
        )
    manifest["fingerprint"] = digest(manifest)
    path = directory / "manifest.json"
    path.write_bytes(canonical(manifest))
    return path
