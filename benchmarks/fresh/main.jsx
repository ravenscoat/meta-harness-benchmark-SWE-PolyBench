import React, {StrictMode,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {useOperationEditor} from './editor.jsx';

async function send(body,scope) {
  const response=await fetch('/operation',{method:'POST',headers:{'Content-Type':'application/json','X-Owner':scope},body:JSON.stringify(body)});
  if(!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function App() {
  const [scope,setScope]=useState('alpha');
  const editor=useOperationEditor({scope,send,initial:'{}'});
  return <main><h1>Operation workspace</h1>
    <label>Owner<select value={scope} onChange={e=>setScope(e.target.value)}><option>alpha</option><option>beta</option></select></label>
    <label>JSON operation<textarea value={editor.draft} onChange={e=>editor.setDraft(e.target.value)}/></label>
    <button onClick={editor.submit}>Submit operation</button>
    <p role="status">{editor.pending?'Working':'Idle'}</p>
    {editor.error && <p role="alert">{editor.error}</p>}
    <output aria-label="Operation result">{editor.result?JSON.stringify(editor.result):''}</output>
  </main>;
}
createRoot(document.getElementById('root')).render(<StrictMode><App/></StrictMode>);
