'use client';

import { useState } from 'react';
import { TaskRows } from '@/components/primitives/task-rows';
import { Drawer } from '@/components/ui/overlay';
import { PassBadge } from '@/components/ui/status-badge';
import { timeAgo } from '@/lib/format';
import type { QAReport } from '@/lib/types';
import { cx } from '@/utils/cx';
import type { QARow } from './qa-page';

function Checks({ report }: { report: QAReport }) {
  return (
    <TaskRows
      rows={report.checks.map((check) => ({
        key: check.name,
        label: check.name,
        status: check.passed ? 'done' : 'failed',
        details: check.details ? [{ label: check.details }] : undefined,
      }))}
    />
  );
}

/** One environment's QA checks, newest report first, with older reports selectable. */
export function QADrawer({ row, onClose }: { row: QARow | null; onClose: () => void }) {
  const [shown, setShown] = useState(row);
  const [index, setIndex] = useState(0);
  if (row !== null && row.id !== shown?.id) {
    setShown(row);
    setIndex(0);
  }
  const report = shown?.reports[index];

  return (
    <Drawer isOpen={row !== null} onClose={onClose} title={shown?.id ?? ''} aria-label="QA report">
      {report && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-body-2-regular text-text-secondary">
            <PassBadge passed={report.passed} />
            <span>
              {report.checks.filter((check) => check.passed).length} of {report.checks.length} checks passed,{' '}
              {timeAgo(report.created_at)}
            </span>
          </div>
          <Checks report={report} />
          {(shown?.reports.length ?? 0) > 1 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-mono-label text-text-tertiary">History</p>
              {shown?.reports.map((item, position) => (
                <button
                  key={item.file}
                  type="button"
                  onClick={() => setIndex(position)}
                  className={cx(
                    'flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-start outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
                    position === index
                      ? 'bg-background-tertiary-default'
                      : 'hover:bg-background-secondary-hover',
                  )}
                >
                  <PassBadge passed={item.passed} />
                  <span className="flex-1 font-mono text-caption-1-medium text-text-secondary">
                    {item.file}
                  </span>
                  <span className="text-caption-1-medium text-text-tertiary">{timeAgo(item.created_at)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
