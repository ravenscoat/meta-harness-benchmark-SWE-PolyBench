import React from 'react';
import {renderHook, act, cleanup} from '@testing-library/react';
import {test, expect, afterEach, vi} from 'vitest';
import {useSyncQueue} from './src/queue.jsx';
afterEach(cleanup);
function store(){const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v),m};}
function op(id,key,title='title',version=1){return {item_id:id,mutation_id:key,title,expected_version:version};}
function ack(operations){return {results:operations.map(o=>({mutation_id:o.mutation_id,status:200,item:{id:o.item_id,title:o.title,version:o.expected_version+1}}))};}
function deferred(){let resolve,reject;let promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject};}
test('durable enqueue, duplicate identity, network retry and reload',async()=>{
 const storage=store();const send=vi.fn().mockRejectedValueOnce(Error('offline')).mockImplementation(async xs=>ack(xs));
 let h=renderHook(()=>useSyncQueue({tenant:'a',send,storage}));
 act(()=>{h.result.current.enqueue(op(1,'one'));h.result.current.enqueue(op(1,'one'));});
 expect(h.result.current.pending.length).toBe(1);
 expect(JSON.parse(storage.getItem('hx-outbox:a')).length).toBe(1);
 expect(()=>h.result.current.enqueue(op(1,'one','other'))).toThrow();
 await act(async()=>h.result.current.flush());expect(h.result.current.error).toBe('offline');expect(h.result.current.pending.length).toBe(1);
 h.unmount();h=renderHook(()=>useSyncQueue({tenant:'a',send,storage}));
 expect(h.result.current.pending.length).toBe(1);
 await act(async()=>h.result.current.flush());expect(h.result.current.pending).toEqual([]);expect(JSON.parse(storage.getItem('hx-outbox:a'))).toEqual([]);
});
test('single-flight flush, concurrent enqueue and version rebasing',async()=>{
 const storage=store(), waiting=deferred();const send=vi.fn().mockImplementationOnce(()=>waiting.promise).mockImplementation(async xs=>ack(xs));
 const h=renderHook(()=>useSyncQueue({tenant:'a',send,storage}));act(()=>h.result.current.enqueue(op(1,'first','first')));
 let p,q;act(()=>{p=h.result.current.flush();q=h.result.current.flush();});expect(p).toBe(q);
 await act(async()=>Promise.resolve());expect(send).toHaveBeenCalledTimes(1);
 act(()=>{h.result.current.enqueue(op(1,'second','second'));h.result.current.enqueue(op(2,'other'));});
 await act(async()=>waiting.resolve(ack([op(1,'first','first')])));await p;
 expect(send.mock.calls[1][0].find(x=>x.mutation_id==='second').expected_version).toBe(2);
 expect(h.result.current.pending).toEqual([]);expect(h.result.current.working).toBe(false);
});
test('invalid acknowledgements never discard operations; conflicts can be discarded and retried',async()=>{
 const storage=store();const send=vi.fn().mockResolvedValueOnce({results:[]}).mockResolvedValueOnce({results:[{mutation_id:'first',status:412}]}).mockImplementation(async xs=>ack(xs));
 const h=renderHook(()=>useSyncQueue({tenant:'a',send,storage}));act(()=>h.result.current.enqueue(op(1,'first')));
 await act(async()=>h.result.current.flush());expect(h.result.current.pending.length).toBe(1);expect(h.result.current.error).toBeTruthy();
 await act(async()=>h.result.current.flush());expect(h.result.current.pending.length).toBe(1);
 act(()=>{h.result.current.discard('first');h.result.current.enqueue(op(1,'retry','new',2));});
 await act(async()=>h.result.current.flush());expect(h.result.current.pending).toEqual([]);
});
test('tenant switch and unmount prevent stale completion from changing either queue',async()=>{
 const storage=store();const d=deferred();const send=vi.fn(()=>d.promise);
 const h=renderHook(({tenant})=>useSyncQueue({tenant,send,storage}),{initialProps:{tenant:'a'}});
 act(()=>h.result.current.enqueue(op(1,'a')));let p;act(()=>{p=h.result.current.flush();});await act(async()=>Promise.resolve());
 h.rerender({tenant:'b'});expect(h.result.current.pending).toEqual([]);act(()=>h.result.current.enqueue(op(2,'b')));
 await act(async()=>d.resolve(ack([op(1,'a')])));await p;
 expect(h.result.current.pending[0].mutation_id).toBe('b');expect(JSON.parse(storage.getItem('hx-outbox:a'))[0].mutation_id).toBe('a');
 h.unmount();const d2=deferred();const h2=renderHook(()=>useSyncQueue({tenant:'b',send:()=>d2.promise,storage}));let p2;act(()=>{p2=h2.result.current.flush();});await act(async()=>Promise.resolve());h2.unmount();
 await act(async()=>d2.resolve(ack([op(2,'b')])));await p2;expect(JSON.parse(storage.getItem('hx-outbox:b')).length).toBe(1);
});
test('corrupt storage and persistence failure do not create phantom entries',()=>{
 const storage=store();storage.setItem('hx-outbox:a','not json');
 const h=renderHook(()=>useSyncQueue({tenant:'a',send:async xs=>ack(xs),storage}));expect(h.result.current.pending).toEqual([]);
 storage.setItem=()=>{throw Error('quota')};expect(()=>h.result.current.enqueue(op(1,'one'))).toThrow('quota');expect(h.result.current.pending).toEqual([]);
});
test('StrictMode does not lose the outbox or duplicate explicit flush',async()=>{
 const storage=store();const send=vi.fn(async xs=>ack(xs));
 const h=renderHook(()=>useSyncQueue({tenant:'a',send,storage}),{wrapper:({children})=><React.StrictMode>{children}</React.StrictMode>});
 act(()=>h.result.current.enqueue(op(1,'strict')));await act(async()=>h.result.current.flush());expect(h.result.current.pending).toEqual([]);expect(send).toHaveBeenCalledTimes(1);
});
