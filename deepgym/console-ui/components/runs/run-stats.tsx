'use client';

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { RunSummary } from '@/lib/types';

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-2xl border border-border-button-default bg-background-secondary-default/70 px-4 py-3 shadow-card">
      <span className="text-mono-label text-text-tertiary">{label}</span>
      <span className="font-mono text-title-2-semibold text-text-primary tabular-nums">{value}</span>
      {hint && <span className="truncate text-caption-1-medium text-text-secondary">{hint}</span>}
    </div>
  );
}

/** Ten score bins (0.0-0.1 ... 0.9-1.0) of the finished runs. */
function histogram(runs: RunSummary[]) {
  const bins = Array.from({ length: 10 }, (_, index) => ({ bin: (index / 10).toFixed(1), runs: 0 }));
  for (const run of runs) {
    if (run.score !== null) bins[Math.min(9, Math.floor(run.score * 10))].runs++;
  }
  return bins;
}

/** Headline numbers and the score distribution for the runs in view. */
export function RunStats({ runs }: { runs: RunSummary[] }) {
  const finished = runs.filter((run) => run.status === 'completed' || run.status === 'failed');
  const passed = finished.filter((run) => run.passed).length;
  const active = runs.length - finished.length;
  const scored = finished.filter((run) => run.score !== null);
  const mean = scored.reduce((sum, run) => sum + (run.score ?? 0), 0) / (scored.length || 1);

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Runs" value={String(runs.length)} hint={`${finished.length} finished`} />
        <Stat
          label="Pass rate"
          value={finished.length ? `${Math.round((passed / finished.length) * 100)}%` : '-'}
          hint={`${passed} passed`}
        />
        <Stat label="Mean score" value={scored.length ? mean.toFixed(2) : '-'} hint="finished runs" />
        <Stat label="In flight" value={String(active)} hint="queued or running" />
      </div>
      <div className="flex min-w-0 flex-col rounded-2xl border border-border-button-default bg-background-secondary-default/70 px-4 pt-3 pb-1 shadow-card">
        <span className="text-mono-label text-text-tertiary">Score distribution</span>
        <div className="h-24">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={histogram(finished)} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="bin"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: 'var(--color-text-tertiary)' }}
                interval={1}
              />
              <Tooltip
                cursor={{ fill: 'var(--color-background-secondary-hover)' }}
                contentStyle={{
                  background: 'var(--color-background-primary-default)',
                  border: '1px solid var(--color-border-button-default)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelFormatter={(bin) => `score ${bin}+`}
              />
              <Bar
                dataKey="runs"
                fill="var(--color-chart-1)"
                radius={[3, 3, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
