import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  /** Small mono label above the title, e.g. a breadcrumb. */
  eyebrow?: ReactNode;
  actions?: ReactNode;
}

/** Page title block with optional eyebrow, description and right-aligned actions. */
export function PageHeader({ title, description, eyebrow, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3 pt-3 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="text-mono-label mb-2 text-text-tertiary">{eyebrow}</div>}
        <h1 className="truncate bg-linear-to-b from-text-primary to-text-secondary bg-clip-text pb-0.5 font-display text-title-1-semibold tracking-tight text-transparent">
          {title}
        </h1>
        {description && <p className="mt-1 text-body-regular text-text-secondary">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
