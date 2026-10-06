import {useEffect, useRef, useState} from 'react';

function validate(op) {
  if (!op || typeof op.mutation_id !== 'string' || !op.mutation_id || op.mutation_id.length > 80 || !Number.isInteger(op.item_id) || op.item_id < 1 || !Number.isInteger(op.expected_version) || op.expected_version < 1 || typeof op.title !== 'string' || !op.title.trim() || op.title.length > 120) throw Error('invalid operation');
  return {mutation_id:op.mutation_id,item_id:op.item_id,expected_version:op.expected_version,title:op.title};
}
const key = tenant => 'hx-outbox:' + tenant;
function load(storage, tenant) {
  try {
    const parsed = JSON.parse(storage.getItem(key(tenant)) || '[]');
    if (!Array.isArray(parsed)) return [];
    const ops = parsed.map(validate);
    if (new Set(ops.map(x => x.mutation_id)).size !== ops.length) return [];
    return ops;
  } catch {return [];}
}

export function useSyncQueue({tenant, send, storage=localStorage}) {
  const holder = useRef(null);
  const mounted = useRef(true);
  if (!holder.current || holder.current.tenant !== tenant || holder.current.storage !== storage) {
    holder.current = {tenant,storage,ops:load(storage,tenant),generation:(holder.current?.generation || 0)+1,promise:null};
  }
  const [view,setView] = useState(() => ({holder:holder.current,pending:holder.current.ops,working:false,error:null}));
  useEffect(() => {
    mounted.current=true;
    return () => {mounted.current=false; holder.current.generation++;};
  }, []);
  const owned = holder.current;
  function publish(ops, working=false, error=null) {
    setView({holder:owned,pending:ops,working,error});
  }
  function persist(ops) {
    owned.storage.setItem(key(owned.tenant),JSON.stringify(ops));
    owned.ops=ops;
  }
  function enqueue(value) {
    const op=validate(value);
    const old=owned.ops.find(x=>x.mutation_id===op.mutation_id);
    if (old) {
      if (JSON.stringify(old)!==JSON.stringify(op)) throw Error('mutation identifier reused');
      return;
    }
    persist([...owned.ops,op]);
    publish(owned.ops,Boolean(owned.promise));
  }
  function discard(id) {
    if (owned.promise) throw Error('cannot discard during flush');
    persist(owned.ops.filter(x=>x.mutation_id!==id)); publish(owned.ops);
  }
  function flush() {
    if (owned.promise) return owned.promise;
    const generation=owned.generation;
    function current() {return mounted.current && holder.current===owned && owned.generation===generation;}
    const promise=Promise.resolve().then(async()=>{
      if (!current()) return;
      publish(owned.ops,true);
      try {
        while (owned.ops.length && current()) {
          const seen=new Set();
          const batch=owned.ops.filter(op=>{if (seen.has(op.item_id)) return false;seen.add(op.item_id);return true;}).slice(0,50);
          const response=await send(batch.map(x=>({...x})),owned.tenant);
          if (!current()) return;
          const results=response?.results;
          if (!Array.isArray(results) || results.length!==batch.length || new Set(results.map(r=>r.mutation_id)).size!==batch.length || results.some(r=>!batch.some(op=>op.mutation_id===r.mutation_id) || ![200,404,409,412].includes(r.status))) throw Error('invalid acknowledgement');
          for (const result of results) {
            const op=batch.find(x=>x.mutation_id===result.mutation_id);
            if (result.status===200 && (!result.item || result.item.id!==op.item_id || result.item.version!==op.expected_version+1)) throw Error('invalid acknowledgement');
          }
          const applied=results.filter(r=>r.status===200);
          const remove=new Set(applied.map(r=>r.mutation_id));
          let remaining=owned.ops.filter(op=>!remove.has(op.mutation_id));
          for (const result of applied) {
            const op=batch.find(x=>x.mutation_id===result.mutation_id);
            remaining=remaining.map(next=>next.item_id===op.item_id && next.expected_version===op.expected_version ? {...next,expected_version:result.item.version} : next);
          }
          persist(remaining);
          if (results.some(r=>r.status!==200)) {publish(owned.ops,false,'synchronization conflict');return;}
          publish(owned.ops,true);
        }
        if (current()) publish(owned.ops);
      } catch (error) {if (current()) publish(owned.ops,false,String(error.message));}
      finally {owned.promise=null;}
    });
    owned.promise=promise;
    return promise;
  }
  const state=view.holder===owned ? view : {pending:owned.ops,working:false,error:null};
  return {pending:state.pending,working:state.working,error:state.error,enqueue,discard,flush};
}
