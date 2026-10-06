"""Evaluator-only original acceptance programs. Never included in worker context."""

from __future__ import annotations

BACKEND = r"""
import os, sqlite3, tempfile, concurrent.futures, json, subprocess, sys
from fastapi.testclient import TestClient
from backend.app import app
client = TestClient(app, raise_server_exceptions=False)
def create(tenant='a', title='card', key=None):
    headers={'X-Tenant':tenant}
    if key: headers['Idempotency-Key']=key
    return client.post('/items',json={'title':title},headers=headers)
def get(id, tenant='a'):
    return client.get(f'/items/{id}',headers={'X-Tenant':tenant})
def patch(id, body, version='1', tenant='a'):
    headers={'X-Tenant':tenant}
    if version is not None: headers['If-Match']=version
    return client.patch(f'/items/{id}',json=body,headers=headers)
def audit(id):
    with sqlite3.connect(os.environ['HX_DB']) as db:
        return db.execute('SELECT count(*) FROM audit WHERE item_id=?',(id,)).fetchone()[0]
def test_idempotency():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        replies=list(pool.map(lambda _: create(key='repeat'),range(12)))
    assert all(r.status_code==201 for r in replies)
    assert len({r.json()['id'] for r in replies})==1
    id=replies[0].json()['id']; assert audit(id)==1
    assert create(title='different',key='repeat').status_code==409
    assert create(tenant='b',key='repeat').json()['id'] != id
    restart = subprocess.run([sys.executable, '-c', "import json; from fastapi.testclient import TestClient; from backend.app import app; r=TestClient(app).post('/items',json={'title':'card'},headers={'X-Tenant':'a','Idempotency-Key':'repeat'}); assert r.status_code==201; print(json.dumps(r.json()))"], capture_output=True, text=True, timeout=20, env=os.environ.copy())
    assert restart.returncode==0, restart.stderr
    assert json.loads(restart.stdout)==replies[0].json()
def test_tenant():
    assert client.post('/items',json={'title':'x'}).status_code==401
    assert create(tenant=' ').status_code==401
    own=create('a','owned').json()['id']; foreign=create('b','foreign').json()['id']
    assert get(foreign).status_code==404
    assert patch(foreign,{'title':'stolen'}).status_code==404
    assert get(own).json()['title']=='owned'
    assert get(foreign,'b').json()['title']=='foreign'
def test_version():
    id=create(title='CAS').json()['id']
    assert patch(id,{'title':'absent'},None).status_code==428
    assert patch(id,{'title':'stale'},'0').status_code==412
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        replies=list(pool.map(lambda n: patch(id,{'title':f'writer-{n}'}),range(8)))
    assert sorted(r.status_code for r in replies)==[200]+[412]*7
    row=get(id); assert row.json()['version']==2 and row.headers['etag']=='2'
    assert audit(id)==2
def test_patch():
    id=create(title='patch').json()['id']
    for body in ({},{'title':None},{'archived':None},{'title':' '},{'title':'x'*121}):
        assert patch(id,body).status_code==422
    assert get(id).json()['version']==1 and audit(id)==1
    assert patch(id,{'archived':True}).json()['archived']==1
    restored=patch(id,{'archived':False},'2'); assert restored.status_code==200
    assert restored.json()['archived']==0 and restored.json()['title']=='patch'
    assert restored.headers['etag']=='3'
def test_archive():
    first=create(title='first').json()['id']; second=create(title='second').json()['id']; foreign=create('b').json()['id']
    def archive(ids): return client.post('/archive',json={'ids':ids},headers={'X-Tenant':'a'})
    assert archive([]).status_code==422
    assert archive([first,foreign]).status_code==404
    assert get(first).json()['archived']==0 and audit(first)==1
    assert archive([first,999999]).status_code==404
    assert get(first).json()['version']==1
    reply=archive([first,first,second]); assert reply.status_code==200 and reply.json()['ids']==[first,second]
    assert get(first).json()['version']==2 and audit(first)==2
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        assert all(r.status_code==200 for r in pool.map(lambda _: archive([first,second]),range(8)))
    assert get(first).json()['version']==2 and audit(first)==2
def test_cursor():
    ids=[create(title=f'Mixed {n}').json()['id'] for n in range(7)]
    def page(**params): return client.get('/items',params=params,headers={'X-Tenant':'a'})
    first=page(limit=2,q='mixed'); assert first.status_code==200
    body=first.json(); assert [i['id'] for i in body['items']]==ids[::-1][:2]
    cursor=body['next_cursor']; assert cursor
    create(title='Mixed newly inserted')
    seen=[i['id'] for i in body['items']]
    for _ in range(8):
        body=page(limit=2,q='mixed',cursor=cursor).json(); seen.extend(i['id'] for i in body['items']); cursor=body['next_cursor']
        if not cursor: break
    assert seen==ids[::-1]
    assert page(cursor='not a cursor').status_code==422
    assert page(cursor=first.json()['next_cursor'],q='other').status_code==422
    assert client.get('/items',params={'cursor':first.json()['next_cursor'],'q':'mixed'},headers={'X-Tenant':'b'}).status_code==422
    assert page(q='%').json()['items']==[]
    assert page(limit=0).status_code==422
"""

FRONTEND = r"""
import React from 'react';
import {renderHook, act, cleanup, waitFor} from '@testing-library/react';
import {test, expect, afterEach, vi} from 'vitest';
import {useSearch, useOptimisticBoard, useEditor} from './src/hooks.jsx';
afterEach(cleanup);
function deferred(){let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};}
const cards=[{id:1,title:'one',version:1},{id:2,title:'two',version:1}];
// GROUP:search
test('latest tenant/query owns results and errors', async()=>{
  const calls=[];const fetcher=vi.fn((q,t)=>{const d=deferred();calls.push({q,t,...d});return d.promise;});
  const h=renderHook(({q,t})=>useSearch(q,t,fetcher),{initialProps:{q:'a',t:'one'}});
  await waitFor(()=>expect(calls.length).toBe(1));
  h.rerender({q:'b',t:'one'});await waitFor(()=>expect(calls.length).toBe(2));
  await act(async()=>calls[1].resolve([{id:2}]));
  await act(async()=>calls[0].resolve([{id:1}]));expect(h.result.current.items).toEqual([{id:2}]);
  h.rerender({q:'b',t:'two'});expect(h.result.current.items).toEqual([]);
  await waitFor(()=>expect(calls.length).toBe(3));
  h.rerender({q:'c',t:'two'});await waitFor(()=>expect(calls.length).toBe(4));
  await act(async()=>calls[3].resolve([{id:4}]));await act(async()=>calls[2].reject(Error('old')));
  expect(h.result.current.items).toEqual([{id:4}]);expect(h.result.current.error).toBe(null);
  h.unmount();
});
test('sync failure recovers and obsolete unmounted work is harmless',async()=>{
  const fetcher=vi.fn().mockImplementationOnce(()=>{throw Error('sync')}).mockResolvedValueOnce([{id:7}]);
  const h=renderHook(({q})=>useSearch(q,'a',fetcher),{initialProps:{q:'bad'}});
  await waitFor(()=>expect(h.result.current.error).toBe('sync'));
  h.rerender({q:'good'});await waitFor(()=>expect(h.result.current.items).toEqual([{id:7}]));
  expect(h.result.current.loading).toBe(false);
});
// GROUP:board
test('rollback is isolated and latest generation wins',async()=>{
  const calls=[];const save=vi.fn(x=>{const d=deferred();calls.push({...d,item:x});return d.promise;});
  const h=renderHook(({initial})=>useOptimisticBoard(initial,save),{initialProps:{initial:cards}});
  let a,b;act(()=>{a=h.result.current.rename(1,'ONE').catch(()=>{});});act(()=>{b=h.result.current.rename(2,'TWO');});
  await act(async()=>calls[1].resolve({...cards[1],title:'TWO',version:2}));
  await act(async()=>calls[0].reject(Error('failed')));await a;await b;
  expect(h.result.current.items.map(x=>x.title)).toEqual(['one','TWO']);
  let old,newer;act(()=>{old=h.result.current.rename(1,'old').catch(()=>{});});act(()=>{newer=h.result.current.rename(1,'new');});
  await act(async()=>calls[3].resolve({...cards[0],title:'new',version:3}));
  await act(async()=>calls[2].resolve({...cards[0],title:'old',version:2}));await old;await newer;
  expect(h.result.current.items[0].title).toBe('new');
});
test('refresh preserves pending edit and stale rejection cannot roll it back',async()=>{
  const calls=[];const save=x=>{const d=deferred();calls.push(d);return d.promise;};
  const h=renderHook(({initial})=>useOptimisticBoard(initial,save),{initialProps:{initial:cards}});
  let old,newer;act(()=>{old=h.result.current.rename(1,'old').catch(()=>{});});act(()=>{newer=h.result.current.rename(1,'new');});
  h.rerender({initial:cards.map(x=>({...x,title:'server-'+x.id}))});
  expect(h.result.current.items[0].title).toBe('new');expect(h.result.current.items[1].title).toBe('server-2');
  await act(async()=>calls[0].reject(Error('obsolete')));await old;expect(h.result.current.items[0].title).toBe('new');
  await act(async()=>calls[1].resolve({...cards[0],title:'new',version:2}));await newer;
});
// GROUP:editor
test('save response preserves typing and session ownership',async()=>{
  const calls=[];const save=x=>{const d=deferred();calls.push(d);return d.promise;};
  const h=renderHook(()=>useEditor(save));act(()=>h.result.current.open(cards[0]));
  let first;act(()=>{first=h.result.current.save();});act(()=>h.result.current.edit('typed later'));
  await act(async()=>calls[0].resolve({...cards[0],title:'saved',version:2}));await first;
  expect(h.result.current.draft.title).toBe('typed later');expect(h.result.current.draft.version).toBe(2);
  let second;act(()=>{second=h.result.current.save();});act(()=>h.result.current.open(cards[1]));
  await act(async()=>calls[1].reject(Error('old session')));await second;
  expect(h.result.current.draft.id).toBe(2);expect(h.result.current.error).toBe(null);expect(h.result.current.saving).toBe(false);
});
test('current failure retries and old successful save cannot change newly opened card',async()=>{
  const calls=[];const save=x=>{const d=deferred();calls.push(d);return d.promise;};
  const h=renderHook(()=>useEditor(save));act(()=>h.result.current.open(cards[0]));
  let first;act(()=>{first=h.result.current.save();});await act(async()=>calls[0].reject(Error('current')));await first;
  expect(h.result.current.error).toBe('current');expect(h.result.current.draft.title).toBe('one');
  let second;act(()=>{second=h.result.current.save();});act(()=>h.result.current.open(cards[1]));
  await act(async()=>calls[1].resolve({...cards[0],version:2}));await second;
  expect(h.result.current.draft.id).toBe(2);h.unmount();
});
"""


def backend_program(groups: list[str]) -> str:
    selected = [g for g in groups if f"def test_{g}():" in BACKEND]
    return BACKEND + "\n" + "\n".join(f"test_{g}()" for g in selected)


def frontend_program(groups: list[str]) -> str:
    prefix, *sections = FRONTEND.split("// GROUP:")
    return (
        prefix
        + "\n"
        + "\n".join(s.split("\n", 1)[1] for s in sections if s.split("\n", 1)[0].strip() in groups)
    )
