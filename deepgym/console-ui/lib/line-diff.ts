/** One row of a unified line diff: old/new line numbers and whether it was kept, added or removed. */
export interface DiffLine {
  type: 'ctx' | 'add' | 'del';
  old: number | null;
  cur: number | null;
  text: string;
}

/**
 * Line diff of `before` -> `after` via a longest-common-subsequence table.
 * ponytail: O(n*m) time and memory; fine for solutions and verifiers (hundreds of lines), use Myers if files get big.
 */
export function lineDiff(before: string, after: string): DiffLine[] {
  const a = before.split('\n');
  const b = after.split('\n');
  const lcs = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const rows: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      rows.push({ type: 'ctx', old: i + 1, cur: j + 1, text: a[i] });
      i++;
      j++;
    } else if (i < a.length && (j === b.length || lcs[i + 1][j] >= lcs[i][j + 1])) {
      rows.push({ type: 'del', old: i + 1, cur: null, text: a[i] });
      i++;
    } else {
      rows.push({ type: 'add', old: null, cur: j + 1, text: b[j] });
      j++;
    }
  }
  return rows;
}
