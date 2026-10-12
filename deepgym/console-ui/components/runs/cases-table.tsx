'use client';

import { RiCheckLine, RiCloseLine, RiListCheck3 } from '@remixicon/react';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { formatDuration, formatScore } from '@/lib/format';
import type { CaseResult } from '@/lib/types';

type CaseRow = CaseResult & { name: string };

const clip = 'block max-w-64 truncate font-mono text-caption-1-medium';

const columns: ColumnDef<CaseRow>[] = [
  {
    id: 'passed',
    accessorFn: (row) => Number(row.passed),
    header: '',
    cell: ({ row }) =>
      row.original.passed ? (
        <RiCheckLine aria-label="passed" className="size-4 text-status-lime-text" />
      ) : (
        <RiCloseLine aria-label="failed" className="size-4 text-status-rose-text" />
      ),
    meta: { className: 'w-8' },
  },
  { id: 'name', accessorKey: 'name', header: 'Case', meta: { className: 'font-mono text-text-primary' } },
  {
    id: 'score',
    accessorKey: 'score',
    header: 'Score',
    cell: ({ row }) => formatScore(row.original.score),
    meta: { align: 'end', className: 'font-mono' },
  },
  {
    id: 'input',
    accessorKey: 'input_summary',
    header: 'Input',
    enableSorting: false,
    cell: ({ row }) => <span className={`${clip} text-text-secondary`}>{row.original.input_summary}</span>,
  },
  {
    id: 'expected',
    accessorKey: 'expected_summary',
    header: 'Expected',
    enableSorting: false,
    cell: ({ row }) => <span className={`${clip} text-text-secondary`}>{row.original.expected_summary}</span>,
  },
  {
    id: 'actual',
    accessorKey: 'actual_summary',
    header: 'Actual',
    enableSorting: false,
    cell: ({ row }) => (
      <span className={`${clip} ${row.original.passed ? 'text-text-secondary' : 'text-text-primary'}`}>
        {row.original.error ?? row.original.actual_summary}
      </span>
    ),
  },
  {
    id: 'time',
    accessorKey: 'execution_time_ms',
    header: 'Time',
    cell: ({ row }) => formatDuration(row.original.execution_time_ms),
    meta: { align: 'end', className: 'font-mono text-text-secondary' },
  },
];

/** Per-case verifier results; failures sort first. */
export function CasesTable({ cases }: { cases: CaseResult[] }) {
  const rows = cases.map((item, index) => ({
    ...item,
    id: String(index),
    name: item.id || `case ${index + 1}`,
  }));
  return (
    <DataTable
      label="Test cases"
      data={rows}
      columns={columns}
      initialSort={[{ id: 'passed', desc: false }]}
      pageSize={25}
      empty={<EmptyState icon={RiListCheck3} title="This verifier reports no per-case results" />}
    />
  );
}
