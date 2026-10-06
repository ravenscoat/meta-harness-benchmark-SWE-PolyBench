import {useEffect, useRef, useState} from 'react';

export function useOperationEditor({scope,send,initial}) {
  const [draft,setDraft]=useState(initial),[result,setResult]=useState(null);
  const [error,setError]=useState(null),[pending,setPending]=useState(false);
  const flight=useRef(null);
  useEffect(()=>{setDraft(initial);setResult(null);setError(null);setPending(false);flight.current=null;},[scope,initial]);
  function submit() {
    if(flight.current) return flight.current;
    let body;
    try {body=JSON.parse(draft);} catch(e) {setError(String(e));return Promise.resolve();}
    setPending(true);setError(null);
    const job=Promise.resolve().then(()=>send(body,scope)).then(reply=>{
      setResult(reply);setDraft('');
    }).catch(e=>setError(String(e))).finally(()=>{setPending(false);flight.current=null;});
    flight.current=job;
    return job;
  }
  return {draft,setDraft,result,error,pending,submit};
}
