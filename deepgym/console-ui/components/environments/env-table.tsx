'use client';

import { RiStackLine } from '@remixicon/react';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { KindBadge } from '@/components/ui/status-badge';
import type { EnvironmentSummary } from '@/lib/types';

const columns: ColumnDef<EnvironmentSummary>[] = [
  {
    id: 'name',
    accessorKey: 'name',
    header: 'Environment',
    cell: ({ row }) => (
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-body-2-medium text-text-primary">{row.original.name}</span>
        <span className="truncate font-mono text-caption-2-medium text-text-tertiary">{row.original.id}</span>
      </div>
    ),
    meta: { className: 'min-w-56' },
  },
  {
    id: 'kind',
    accessorKey: 'kind',
    header: 'Kind',
    cell: ({ row }) => <KindBadge kind={row.original.kind} />,
  },
  { id: 'domain', accessorKey: 'domain', header: 'Domain', meta: { className: 'text-text-secondary' } },
  {
    id: 'difficulty',
    accessorKey: 'difficulty',
    header: 'Difficulty',
    meta: { className: 'text-text-secondary' },
  },
  {
    id: 'family',
    accessorKey: 'family',
    header: 'Family',
    meta: { className: 'whitespace-nowrap text-text-secondary' },
  },
  {
    id: 'tags',
    accessorFn: (env) => env.tags.join(' '),
    header: 'Tags',
    enableSorting: false,
    cell: ({ row }) => (
      <span className="block max-w-56 truncate text-caption-1-medium text-text-tertiary">
        {row.original.tags.join(', ')}
      </span>
    ),
  },
  {
    id: 'variants',
    accessorKey: 'variants',
    header: 'Variants',
    meta: { align: 'end', className: 'font-mono text-text-secondary' },
  },
];

interface EnvTableProps {
  rows: EnvironmentSummary[];
  loading: boolean;
  onOpen: (env: EnvironmentSummary) => void;
}

/** Registry table; Enter or click opens an environment. */
export function EnvTable({ rows, loading, onOpen }: EnvTableProps) {
  return (
    <DataTable
      label="Environments"
      data={rows}
      columns={columns}
      onRowAction={onOpen}
      pageSize={50}
      empty={
        <EmptyState icon={RiStackLine} title={loading ? 'Loading environments' : 'No environments match'}>
          {loading ? null : 'Clear the search or filters to see every environment.'}
        </EmptyState>
      }
    />
  );
}
