import type { ReactNode } from 'react';
import { PassBadge, RunStatusBadge } from '@/components/ui/status-badge';
import { formatDuration, formatScore } from '@/lib/format';
import type { RunDetail } from '@/lib/types';

function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 px-4 py-3">
      <span className="text-mono-label text-text-tertiary">{label}</span>
      <div className="flex min-h-6 items-center truncate text-body-medium text-text-primary">{children}</div>
    </div>
  );
}

/** One strip of the run's headline facts. */
export function RunSummary({ run }: { run: RunDetail }) {
  return (
    <div className="grid grid-cols-2 divide-separator-border overflow-hidden rounded-2xl border border-border-button-default bg-background-secondary-default/70 shadow-card sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
      <Metric label="Status">
        <RunStatusBadge status={run.status} />
      </Metric>
      <Metric label="Score">
        <span className="font-mono text-title-2-semibold tabular-nums">{formatScore(run.score)}</span>
      </Metric>
      <Metric label="Result">
        <PassBadge passed={run.passed} />
      </Metric>
      <Metric label="Duration">
        <span className="font-mono">{formatDuration(run.duration_ms)}</span>
      </Metric>
      <Metric label="Provider">
        <span className="font-mono">
          {run.provider}
          {run.mode !== run.provider && <span className="text-text-tertiary"> ({run.mode})</span>}
        </span>
      </Metric>
      <Metric label="Error type">
        <span className="font-mono text-text-error-primary">
          {run.error_type ?? <span className="text-text-tertiary">-</span>}
        </span>
      </Metric>
    </div>
  );
}
