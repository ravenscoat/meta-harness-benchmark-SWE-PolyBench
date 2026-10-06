import {useEffect, useRef, useState} from 'react';

export function useOperationEditor({scope,send,initial}) {
  const [draft,setDraftState]=useState(initial),[result,setResult]=useState(null);
  const [error,setError]=useState(null),[pending,setPending]=useState(false);
  const current=useRef(draft),epoch=useRef(0),alive=useRef(false),flight=useRef(null);
  function setDraft(value) {setDraftState(previous=>{
    const next=typeof value==='function'?value(previous):value;
    current.current=next;return next;
  });}
  useEffect(()=>{
    alive.current=true;epoch.current++;current.current=initial;flight.current=null;
    setDraftState(initial);setResult(null);setError(null);setPending(false);
    return ()=>{alive.current=false;epoch.current++;flight.current=null;};
  },[scope,initial]);
  function submit() {
    if(flight.current) return flight.current;
    const submitted=current.current,stamp=epoch.current;
    let body;
    try {body=JSON.parse(submitted);} catch(e) {setError(String(e));return Promise.resolve();}
    const valid=()=>alive.current && epoch.current===stamp;
    setPending(true);setError(null);
    const job=Promise.resolve().then(()=>send(body,scope)).then(reply=>{
      if(!valid()) return;
      setResult(reply);
      if(current.current===submitted) {current.current='';setDraftState('');}
    }).catch(e=>{if(valid()) setError(String(e));}).finally(()=>{
      if(valid() && flight.current===job) {setPending(false);flight.current=null;}
    });
    flight.current=job;return job;
  }
  return {draft,setDraft,result,error,pending,submit};
}
