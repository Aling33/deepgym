'use client';

import { useState } from 'react';
import { TaskRows } from '@/components/primitives/task-rows';
import { Drawer } from '@/components/ui/overlay';
import { timeAgo } from '@/lib/format';
import type { QAReport } from '@/lib/types';
import { QAStatusBadge } from './qa-status';

/** One environment's QA checks; a check's details expand under it. */
export function QADrawer({ report, onClose }: { report: QAReport | null; onClose: () => void }) {
  // Keep the last report while the drawer animates closed.
  const [shown, setShown] = useState(report);
  const changed = report?.environment !== shown?.environment || report?.created_at !== shown?.created_at;
  if (report !== null && changed) setShown(report);

  return (
    <Drawer
      isOpen={report !== null}
      onClose={onClose}
      title={shown?.environment ?? ''}
      aria-label="QA report"
    >
      {shown && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-body-2-regular text-text-secondary">
            <QAStatusBadge report={shown} />
            <span>
              {shown.checks.filter((check) => check.passed).length} of {shown.checks.length} checks passed,{' '}
              {timeAgo(shown.created_at)}
            </span>
          </div>
          <TaskRows
            rows={shown.checks.map((check) => ({
              key: check.name,
              label: check.name,
              status: check.passed ? 'done' : 'failed',
              details: check.details ? [{ label: check.details }] : undefined,
            }))}
          />
        </div>
      )}
    </Drawer>
  );
}
