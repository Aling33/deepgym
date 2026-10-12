'use client';

import { RiShieldCheckLine } from '@remixicon/react';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { DataTable } from '@/components/ui/data-table';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { PassBadge } from '@/components/ui/status-badge';
import { useApi } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import type { QAReport } from '@/lib/types';
import { useQueryParam } from '@/lib/use-query-param';
import { QADrawer } from './qa-drawer';

/** One row per environment: its newest report plus how many it has. */
export interface QARow {
  id: string;
  latest: QAReport;
  reports: QAReport[];
}

const columns: ColumnDef<QARow>[] = [
  { id: 'id', accessorKey: 'id', header: 'Environment', meta: { className: 'font-mono text-text-primary' } },
  {
    id: 'passed',
    accessorFn: (row) => Number(row.latest.passed),
    header: 'Latest',
    cell: ({ row }) => <PassBadge passed={row.original.latest.passed} />,
  },
  {
    id: 'checks',
    accessorFn: (row) =>
      row.latest.checks.filter((check) => check.passed).length / (row.latest.checks.length || 1),
    header: 'Checks passed',
    cell: ({ row }) => {
      const { checks } = row.original.latest;
      return `${checks.filter((check) => check.passed).length} / ${checks.length}`;
    },
    meta: { className: 'font-mono text-text-secondary' },
  },
  {
    id: 'created',
    accessorFn: (row) => row.latest.created_at,
    header: 'Checked',
    cell: ({ row }) => timeAgo(row.original.latest.created_at),
    meta: { className: 'text-text-secondary' },
  },
  {
    id: 'reports',
    accessorFn: (row) => row.reports.length,
    header: 'Reports',
    meta: { align: 'end', className: 'font-mono text-text-secondary' },
  },
];

/** QA reports grouped per environment (newest first); a row opens its checks (?env=). */
export function QAPage() {
  const { data, error } = useApi<QAReport[]>('/qa', 15_000);
  const [selected, setSelected] = useQueryParam('env');
  const rows = useMemo(() => {
    const groups = Map.groupBy(data ?? [], (report) => report.environment);
    return [...groups].map(([id, reports]): QARow => ({ id, latest: reports[0], reports }));
  }, [data]);

  return (
    <>
      <PageHeader
        title="QA"
        description="Reward-hacking and verifier checks per environment, from the reports deepgym qa writes."
      />
      <Card flush>
        <DataTable
          label="QA reports"
          data={rows}
          columns={columns}
          onRowAction={(row) => setSelected(row.id)}
          initialSort={[{ id: 'passed', desc: false }]}
          empty={
            <EmptyState
              icon={RiShieldCheckLine}
              title={error ? 'Could not load QA reports' : 'No QA reports yet'}
            >
              {error ?? (
                <>
                  Reports are read from{' '}
                  <code className="font-mono text-text-primary">~/.deepgym/qa/*.json</code>.
                </>
              )}
            </EmptyState>
          }
        />
      </Card>
      <QADrawer row={rows.find((row) => row.id === selected) ?? null} onClose={() => setSelected(null)} />
    </>
  );
}
