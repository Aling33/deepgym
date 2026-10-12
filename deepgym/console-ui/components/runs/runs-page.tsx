'use client';

import { RiAddLine, RiCloseLine } from '@remixicon/react';
import { useRouter } from 'next/navigation';
import { Chip } from '@/components/base/badges/chip';
import { Button } from '@/components/base/buttons/button';
import {
  SegmentedControl,
  SegmentedControlItem,
} from '@/components/base/segmented-control/segmented-control';
import { Card } from '@/components/ui/card';
import { FilterSelect } from '@/components/ui/filter-select';
import { PageHeader } from '@/components/ui/page-header';
import { useApi } from '@/lib/api';
import { RUN_MODES, type RunSummary } from '@/lib/types';
import { useHotkey } from '@/lib/use-hotkey';
import { useQueryParam } from '@/lib/use-query-param';
import { NewRunDialog } from './new-run-dialog';
import { RunStats } from './run-stats';
import { RunsTable } from './runs-table';

const STATUSES = ['all', 'queued', 'running', 'completed', 'failed'] as const;
const PROVIDERS = RUN_MODES.filter((mode) => mode !== 'auto');

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <Chip variant="caption" color="blue" className="gap-1 ps-2 pe-1">
      <span className="font-mono">{label}</span>
      <button
        type="button"
        aria-label={`Clear ${label}`}
        onClick={onClear}
        className="flex cursor-pointer rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring"
      >
        <RiCloseLine aria-hidden className="size-3.5" />
      </button>
    </Chip>
  );
}

/** Runs table with status, provider, environment and eval-group filters, plus the New run dialog (?new=). */
export function RunsPage() {
  const router = useRouter();
  const [status, setStatus] = useQueryParam('status');
  const [provider, setProvider] = useQueryParam('provider');
  const [environment, setEnvironment] = useQueryParam('environment');
  const [group, setGroup] = useQueryParam('group');
  const [newRun, setNewRun] = useQueryParam('new');
  useHotkey('n', () => setNewRun('1'), newRun === null);

  const params = new URLSearchParams({ limit: '500' });
  if (status) params.set('status', status);
  if (provider) params.set('provider', provider);
  if (environment) params.set('environment', environment);
  if (group) params.set('group_id', group);
  const { data, error } = useApi<RunSummary[]>(`/runs?${params}`, 2500);
  const runs = data ?? [];

  return (
    <>
      <PageHeader
        title="Runs"
        description="Score a solution, or a reference, against one environment or a small eval. Updates live."
        actions={
          <Button leadingIcon={RiAddLine} onClick={() => setNewRun('1')}>
            New run
          </Button>
        }
      />
      <RunStats runs={runs} />
      <Card flush className="mt-4">
        <div className="flex flex-wrap items-center gap-2 p-3">
          <div className="scrollbar-thin max-w-full overflow-x-auto">
            <SegmentedControl
              aria-label="Status"
              selectedKeys={[status ?? 'all']}
              onSelectionChange={(keys) => {
                const next = [...keys][0];
                setStatus(next === 'all' ? null : String(next));
              }}
            >
              {STATUSES.map((value) => (
                <SegmentedControlItem key={value} id={value}>
                  {value}
                </SegmentedControlItem>
              ))}
            </SegmentedControl>
          </div>
          <FilterSelect label="providers" value={provider} options={[...PROVIDERS]} onChange={setProvider} />
          {environment && <FilterChip label={environment} onClear={() => setEnvironment(null)} />}
          {group && <FilterChip label={`eval ${group}`} onClear={() => setGroup(null)} />}
          <span className="ms-auto font-mono text-caption-1-medium text-text-tertiary">
            {runs.length} runs
          </span>
        </div>
        <RunsTable
          runs={runs}
          loading={!data && !error}
          error={error}
          onOpen={(run) => router.push(`/runs/detail/?id=${run.id}`)}
        />
      </Card>
      <NewRunDialog
        open={newRun !== null}
        initialEnv={newRun && newRun !== '1' ? newRun : null}
        onClose={() => setNewRun(null)}
        onCreated={(created) =>
          created.length === 1
            ? router.push(`/runs/detail/?id=${created[0].id}`)
            : router.replace(`/runs/?group=${created[0].group_id}`)
        }
      />
    </>
  );
}
