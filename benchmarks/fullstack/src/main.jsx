import React from 'react';
import {createRoot} from 'react-dom/client';
import {useSearch, useOptimisticBoard, useEditor} from './hooks.jsx';
import './style.css';
const api = {
  search: (query, tenant) => fetch(`/items?q=${encodeURIComponent(query)}`, {headers:{'X-Tenant':tenant}}).then(async r => {if (!r.ok) throw Error(String(r.status)); return (await r.json()).items;}),
  save: item => fetch(`/items/${item.id}`, {method:'PATCH', headers:{'Content-Type':'application/json', 'X-Tenant':'a', 'If-Match':String(item.version)}, body:JSON.stringify({title:item.title})}).then(async r => {if (!r.ok) throw Error(String(r.status)); return r.json();})
};
function App() {
  const [query, setQuery] = React.useState('');
  const [refresh, setRefresh] = React.useState(0);
  const fetcher = React.useCallback((q, tenant) => api.search(q, tenant), [refresh]);
  const search = useSearch(query, 'a', fetcher);
  const board = useOptimisticBoard(search.items, api.save);
  const editor = useEditor(api.save);
  return <main><h1>HX Workspace</h1><label>Search<input value={query} onChange={e => setQuery(e.target.value)}/></label>
    {search.error && <p role="alert">{search.error}</p>}
    <ul>{board.items.map(item => <li key={item.id}><button onClick={() => editor.open(item)}>{item.title}</button></li>)}</ul>
    {editor.draft && <form onSubmit={async e => {e.preventDefault(); if (await editor.save()) setRefresh(n => n + 1);}}><input aria-label="Title" value={editor.draft.title} onChange={e => editor.edit(e.target.value)}/><button disabled={editor.saving}>Save</button>{editor.error && <p role="alert">{editor.error}</p>}</form>}
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
