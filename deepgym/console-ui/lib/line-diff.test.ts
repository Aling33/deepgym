import { expect, test } from 'bun:test';
import { lineDiff } from './line-diff';

test('marks kept, removed and added lines with both line numbers', () => {
  const rows = lineDiff('a\nb\nc', 'a\nx\nc\nd');
  expect(rows.map((row) => `${row.type}:${row.text}`)).toEqual(['ctx:a', 'del:b', 'add:x', 'ctx:c', 'add:d']);
  expect(rows[1]).toEqual({ type: 'del', old: 2, cur: null, text: 'b' });
  expect(rows[4]).toEqual({ type: 'add', old: null, cur: 4, text: 'd' });
});

test('identical text is all context', () => {
  expect(lineDiff('same\ntext', 'same\ntext').every((row) => row.type === 'ctx')).toBe(true);
});
