import type { ReactNode } from 'react';
import { cx } from '@/utils/cx';

interface CardProps {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Drop the body padding, e.g. for an edge-to-edge table. */
  flush?: boolean;
}

/** Translucent panel (BoardUI card recipe) with an optional mono title row. */
export function Card({ title, actions, children, className, flush }: CardProps) {
  return (
    <section
      className={cx(
        'min-w-0 overflow-hidden rounded-3xl border border-border-button-default bg-background-secondary-default/70 shadow-card backdrop-blur-sm',
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex min-h-11 items-center justify-between gap-3 px-4 py-2">
          <h2 className="text-mono-label text-text-tertiary">{title}</h2>
          {actions}
        </header>
      )}
      <div className={flush ? undefined : 'p-4 pt-0'}>{children}</div>
    </section>
  );
}
