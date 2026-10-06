import {renderHook,act} from '@testing-library/react';
import {expect,it} from 'vitest';
import {useOperationEditor} from './editor.jsx';
it('shows editable draft and does not submit on mount',()=>{
  let calls=0;
  const send=()=>{calls++;return Promise.resolve({ok:true});};
  const {result}=renderHook(()=>useOperationEditor({scope:'alpha',send,initial:'{}'}));
  expect(result.current.draft).toBe('{}');
  act(()=>result.current.setDraft('{"key":"new"}'));
  expect(result.current.draft).toContain('new');
  expect(calls).toBe(0);
});
