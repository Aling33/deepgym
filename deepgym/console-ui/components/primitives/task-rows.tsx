'use client';
// Adapted from Beautiful UI "Task Rows" (https://beautifului.dev), MIT. See ./LICENSE.
// Changes: driven by real statuses instead of a demo timeline, links per row, BoardUI tokens.

import { RiArrowDownSLine, RiCheckLine, RiCloseLine } from '@remixicon/react';
import Link from 'next/link';
import { type ReactNode, useState } from 'react';
import { cx } from '@/utils/cx';

export type TaskStatus = 'done' | 'failed' | 'running' | 'queued';

export interface TaskRow {
  key: string;
  label: ReactNode;
  /** Right-aligned mono value, e.g. a score. */
  meta?: string;
  status: TaskStatus;
  /** Lines revealed when the row is expanded. */
  details?: { label: string; meta?: string }[];
  /** Navigate here when the row has no details to expand. */
  href?: string;
}

function Ring({ active }: { active: boolean }) {
  return (
    <span className="relative inline-flex size-5 shrink-0">
      <svg aria-hidden viewBox="0 0 20 20" className={cx('size-5', active && 'animate-spin')}>
        <circle cx="10" cy="10" r="8" fill="none" stroke="var(--color-separator-border)" strokeWidth="2" />
        {active && (
          <circle
            cx="10"
            cy="10"
            r="8"
            fill="none"
            stroke="var(--color-accent-400)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="14 36"
          />
        )}
      </svg>
    </span>
  );
}

function StatusMark({ status }: { status: TaskStatus }) {
  if (status === 'running' || status === 'queued') return <Ring active={status === 'running'} />;
  const done = status === 'done';
  const Icon = done ? RiCheckLine : RiCloseLine;
  return (
    <span
      className={cx(
        'flex size-5 shrink-0 items-center justify-center rounded-full text-text-white',
        done ? 'bg-status-lime-text' : 'bg-status-rose-text',
      )}
    >
      <Icon aria-hidden className="size-3.5" />
    </span>
  );
}

const PILL: Record<TaskStatus, { text: string; className: string }> = {
  done: { text: 'Passed', className: 'bg-status-lime-background text-status-lime-text' },
  failed: { text: 'Failed', className: 'bg-status-rose-background text-status-rose-text' },
  running: { text: 'Running', className: 'bg-status-blue-background text-status-blue-text' },
  queued: { text: 'Queued', className: 'bg-background-tertiary-default text-text-secondary' },
};

function RowBody({ row, open }: { row: TaskRow; open?: boolean }) {
  return (
    <>
      <StatusMark status={row.status} />
      <span className="min-w-0 flex-1 truncate text-body-2-medium text-text-primary">{row.label}</span>
      {row.meta && (
        <span className="font-mono text-caption-1-medium text-text-secondary tabular-nums">{row.meta}</span>
      )}
      <span
        className={cx(
          'inline-flex h-5 items-center rounded-full px-2 text-caption-1-medium',
          PILL[row.status].className,
        )}
      >
        {PILL[row.status].text}
      </span>
      {open !== undefined && (
        <RiArrowDownSLine
          aria-hidden
          className={cx(
            'size-4 shrink-0 text-foreground-icon-secondary transition-transform',
            open && 'rotate-180',
          )}
        />
      )}
    </>
  );
}

/** Compact status list: one row per task, expandable into detail lines. */
export function TaskRows({ rows, className }: { rows: TaskRow[]; className?: string }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const rowClass =
    'flex h-10 w-full items-center gap-2.5 px-3 text-start outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-border-focus-ring';

  return (
    <div
      className={cx(
        'flex w-full flex-col overflow-hidden rounded-2xl border border-border-button-default bg-background-primary-default shadow-card',
        className,
      )}
    >
      {rows.map((row, index) => {
        const expanded = open[row.key] ?? false;
        return (
          <div
            key={row.key}
            className="border-b border-separator-border transition-colors last:border-0 hover:bg-background-secondary-hover"
            style={{
              animation: `fade-up 400ms cubic-bezier(0.23,1,0.32,1) ${Math.min(index, 10) * 40}ms both`,
            }}
          >
            {row.details?.length ? (
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen((current) => ({ ...current, [row.key]: !expanded }))}
                className={cx(rowClass, 'cursor-pointer')}
              >
                <RowBody row={row} open={expanded} />
              </button>
            ) : row.href ? (
              <Link href={row.href} className={rowClass}>
                <RowBody row={row} />
              </Link>
            ) : (
              <div className={rowClass}>
                <RowBody row={row} />
              </div>
            )}
            {row.details?.length ? (
              <div
                className="grid transition-[grid-template-rows,opacity] duration-300"
                style={{ gridTemplateRows: expanded ? '1fr' : '0fr', opacity: expanded ? 1 : 0 }}
              >
                <div className="overflow-hidden">
                  <div className="mb-2.5 grid grid-cols-[20px_1fr] gap-2.5 px-3">
                    <span aria-hidden className="mx-auto h-full w-px bg-separator-border" />
                    <div className="flex flex-col gap-1.5">
                      {row.details.map((detail) => (
                        <div key={detail.label} className="flex items-start justify-between gap-3">
                          <span className="text-caption-1-medium whitespace-pre-wrap text-text-secondary">
                            {detail.label}
                          </span>
                          {detail.meta && (
                            <span className="shrink-0 font-mono text-caption-1-medium text-text-tertiary">
                              {detail.meta}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
