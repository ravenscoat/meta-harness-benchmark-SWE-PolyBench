import React from 'react';
import {renderHook, act, cleanup} from '@testing-library/react';
import {afterEach, expect, test} from 'vitest';
import {useEditor} from './hooks.jsx';
afterEach(cleanup);
test('opening and editing a card remains available', () => {
  const {result} = renderHook(() => useEditor(async x => x));
  act(() => result.current.open({id:1, title:'hello', version:1}));
  act(() => result.current.edit('changed'));
  expect(result.current.draft.title).toBe('changed');
});
