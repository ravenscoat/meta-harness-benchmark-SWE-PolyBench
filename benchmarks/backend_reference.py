"""Reference implementation for an original HX transactional workspace benchmark.

This is evaluator material, excluded from worker repositories and proposer history.
"""
import base64
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel

app = FastAPI()


@contextmanager
def connection():
    db = sqlite3.connect(os.environ['HX_DB'], timeout=20)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, title TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, updated INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS requests(tenant TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(tenant,key));
      CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, item_id INTEGER NOT NULL, kind TEXT NOT NULL);
    ''')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


class Create(BaseModel):
    title: str


class Change(BaseModel):
    title: str | None = None
    archived: bool | None = None


class Batch(BaseModel):
    ids: list[int]


def valid_title(title):
    if not title.strip() or len(title) > 120:
        raise HTTPException(422, 'invalid title')
    return title


def tenant_value(tenant):
    if not tenant or not tenant.strip():
        raise HTTPException(401, 'tenant required')
    return tenant


def lookup(db, tenant, item_id):
    row = db.execute('SELECT * FROM items WHERE tenant=? AND id=?', (tenant, item_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'not found')
    return dict(row)


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/items', status_code=201)
def create(body: Create, x_tenant: str | None = Header(None), idempotency_key: str | None = Header(None)):
    tenant = tenant_value(x_tenant)
    title = valid_title(body.title)
    digest = hashlib.sha256(json.dumps({'title':title}, sort_keys=True).encode()).hexdigest()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if idempotency_key:
            row = db.execute('SELECT * FROM requests WHERE tenant=? AND key=?', (tenant, idempotency_key)).fetchone()
            if row:
                if row['digest'] != digest:
                    raise HTTPException(409, 'key reused with different payload')
                return json.loads(row['body'])
        cursor = db.execute('INSERT INTO items(tenant,title) VALUES(?,?)', (tenant,title))
        result = lookup(db, tenant, cursor.lastrowid)
        db.execute('INSERT INTO audit(tenant,item_id,kind) VALUES(?,?,?)', (tenant,result['id'],'create'))
        if idempotency_key:
            db.execute('INSERT INTO requests VALUES(?,?,?,?)', (tenant,idempotency_key,digest,json.dumps(result)))
        return result


@app.get('/items/{item_id}')
def get_item(item_id: int, response: Response, x_tenant: str | None = Header(None)):
    with connection() as db:
        result = lookup(db, tenant_value(x_tenant), item_id)
        response.headers['ETag'] = str(result['version'])
        return result


@app.patch('/items/{item_id}')
def patch(item_id: int, body: Change, response: Response, x_tenant: str | None = Header(None), if_match: str | None = Header(None)):
    tenant = tenant_value(x_tenant)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = lookup(db, tenant, item_id)
        if if_match is None:
            raise HTTPException(428, 'If-Match required')
        if if_match != str(current['version']):
            raise HTTPException(412, 'stale version')
        supplied = body.model_fields_set
        if not supplied or (('title' in supplied and body.title is None) or ('archived' in supplied and body.archived is None)):
            raise HTTPException(422, 'nonempty patch; null is forbidden')
        title = valid_title(body.title) if 'title' in supplied else current['title']
        archived = int(body.archived) if 'archived' in supplied else current['archived']
        db.execute('UPDATE items SET title=?,archived=?,version=version+1,updated=updated+1 WHERE tenant=? AND id=?', (title,archived,tenant,item_id))
        db.execute('INSERT INTO audit(tenant,item_id,kind) VALUES(?,?,?)', (tenant,item_id,'patch'))
        result = lookup(db, tenant, item_id)
        response.headers['ETag'] = str(result['version'])
        return result


@app.post('/archive')
def archive(body: Batch, x_tenant: str | None = Header(None)):
    tenant = tenant_value(x_tenant)
    ids = list(dict.fromkeys(body.ids))
    if not ids or len(ids) > 100:
        raise HTTPException(422, 'invalid batch')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = [lookup(db,tenant,item_id) for item_id in ids]
        for row in rows:
            if not row['archived']:
                db.execute('UPDATE items SET archived=1,version=version+1,updated=updated+1 WHERE tenant=? AND id=?', (tenant,row['id']))
                db.execute('INSERT INTO audit(tenant,item_id,kind) VALUES(?,?,?)', (tenant,row['id'],'archive'))
        return {'ids':ids}


@app.get('/items')
def listing(x_tenant: str | None = Header(None), limit: int = Query(2,ge=1,le=20), cursor: str | None = None, q: str = ''):
    tenant = tenant_value(x_tenant)
    anchor = None
    if cursor:
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor)%4)))
            if payload['tenant'] != tenant or payload['q'] != q or not isinstance(payload['updated'],int) or not isinstance(payload['id'],int):
                raise ValueError()
            anchor = (payload['updated'],payload['id'])
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            raise HTTPException(422,'invalid cursor') from None
    with connection() as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM items WHERE tenant=? AND archived=0 ORDER BY updated DESC,id DESC',(tenant,))]
    rows = [r for r in rows if q.casefold() in r['title'].casefold() and (anchor is None or (r['updated'],r['id']) < anchor)]
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = base64.urlsafe_b64encode(json.dumps({'tenant':tenant,'q':q,'updated':last['updated'],'id':last['id']}).encode()).decode().rstrip('=')
    return {'items':page,'next_cursor':next_cursor}
