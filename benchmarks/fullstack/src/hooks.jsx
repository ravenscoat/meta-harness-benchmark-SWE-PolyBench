import {useEffect, useRef, useState} from 'react';

export function useSearch(query, tenant, fetcher) {
  const [state, setState] = useState({items: [], error: null, loading: false});
  useEffect(() => {
    let current = true;
    setState({items: [], error: null, loading: true});
    Promise.resolve().then(() => fetcher(query, tenant)).then(
      items => {if (current) setState({items, error: null, loading: false});},
      error => {if (current) setState({items: [], error: String(error.message), loading: false});}
    );
    return () => {current = false;};
  }, [query, tenant, fetcher]);
  return state;
}

export function useOptimisticBoard(initial, saveItem) {
  const [items, setItems] = useState(initial);
  const pending = useRef(new Map());
  const sequence = useRef(0);
  useEffect(() => {
    setItems(current => initial.map(item => pending.current.has(item.id) ? (current.find(i => i.id === item.id) || item) : item));
  }, [initial]);
  async function rename(id, title) {
    const token = ++sequence.current;
    let before;
    setItems(current => {before = current.find(i => i.id === id); return current.map(i => i.id === id ? {...i, title} : i);});
    // Updater functions can be deferred; obtain a stable current item from a ref below.
    before = latest.current.find(i => i.id === id);
    if (!before) throw Error('missing item');
    pending.current.set(id, token);
    try {
      const result = await saveItem({...before, title});
      if (pending.current.get(id) === token) {
        pending.current.delete(id);
        setItems(current => current.map(i => i.id === id ? result : i));
      }
      return result;
    } catch (error) {
      if (pending.current.get(id) === token) {
        pending.current.delete(id);
        setItems(current => current.map(i => i.id === id ? before : i));
      }
      throw error;
    }
  }
  const latest = useRef(items);
  latest.current = items;
  return {items, rename};
}

export function useEditor(saveItem) {
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const session = useRef(0);
  const revision = useRef(0);
  const live = useRef(true);
  const latest = useRef(draft);
  latest.current = draft;
  useEffect(() => {live.current = true; return () => {live.current = false; ++session.current;};}, []);
  function open(item) {++session.current; revision.current = 0; setDraft({...item}); setError(null); setSaving(false);}
  function edit(title) {++revision.current; setDraft(item => item && ({...item, title}));}
  async function save() {
    if (!latest.current) return;
    const startedSession = session.current, startedRevision = revision.current;
    const snapshot = {...latest.current};
    setSaving(true); setError(null);
    try {
      const result = await saveItem(snapshot);
      if (live.current && session.current === startedSession) {
        setDraft(current => revision.current === startedRevision ? {...result} : {...current, version:result.version});
        setSaving(false);
      }
      return result;
    } catch (failure) {
      if (live.current && session.current === startedSession) {setError(String(failure.message)); setSaving(false);}
    }
  }
  return {draft, error, saving, open, edit, save};
}
