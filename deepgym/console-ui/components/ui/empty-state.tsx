import type { RemixiconComponentType } from '@remixicon/react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: RemixiconComponentType;
  title: string;
  children?: ReactNode;
}

/** Centered placeholder for empty lists and failed loads. */
export function EmptyState({ icon: Icon, title, children }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <div className="mb-1 flex size-10 items-center justify-center rounded-2lg border border-border-button-default bg-background-primary-default shadow-xs">
        <Icon aria-hidden className="size-5 text-foreground-icon-secondary" />
      </div>
      <p className="text-body-medium text-text-primary">{title}</p>
      {children && <div className="max-w-md text-body-regular text-text-secondary">{children}</div>}
    </div>
  );
}
