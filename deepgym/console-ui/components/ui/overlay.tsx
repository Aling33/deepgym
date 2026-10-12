'use client';

import type { ReactNode } from 'react';
import { Modal as AriaModal, Dialog, ModalOverlay } from 'react-aria-components';
import { CloseButton } from '@/components/base/buttons/close-button';
import { cx } from '@/utils/cx';

interface OverlayProps {
  isOpen: boolean;
  onClose: () => void;
  /** Accessible name and visible heading. */
  title: ReactNode;
  /** Plain-text name for assistive tech when `title` is not a string. */
  'aria-label'?: string;
  /** Rendered under the heading. */
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

const scrim = (state: { isEntering: boolean; isExiting: boolean }) =>
  cx(
    'fixed inset-0 z-50 flex bg-black/45 backdrop-blur-[2px] transition-opacity duration-200',
    (state.isEntering || state.isExiting) && 'opacity-0',
  );

function Header({ title, description, onClose }: Pick<OverlayProps, 'title' | 'description' | 'onClose'>) {
  return (
    <header className="flex items-start gap-3 border-b border-separator-border px-5 py-4">
      <div className="min-w-0 flex-1">
        <h2 slot="title" className="font-display text-title-3-semibold text-text-primary">
          {title}
        </h2>
        {description && <div className="mt-0.5 text-body-regular text-text-secondary">{description}</div>}
      </div>
      <CloseButton size="md" aria-label="Close" onClick={onClose} />
    </header>
  );
}

/** Centered dialog (react-aria modal: focus trap, Esc to close) on BoardUI surfaces. */
export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  ...rest
}: OverlayProps) {
  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={(open) => !open && onClose()}
      isDismissable
      className={(state) => cx(scrim(state), 'items-end justify-center p-3 sm:items-center sm:p-6')}
    >
      <AriaModal
        className={(state) =>
          cx(
            'flex max-h-[calc(100dvh-24px)] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-border-button-default bg-background-secondary-default shadow-xl transition duration-200 ease-out',
            (state.isEntering || state.isExiting) && 'translate-y-2 scale-[0.98] opacity-0',
            className,
          )
        }
      >
        <Dialog aria-label={rest['aria-label']} className="flex min-h-0 flex-1 flex-col outline-none">
          <Header title={title} description={description} onClose={onClose} />
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && (
            <footer className="flex items-center justify-end gap-2 border-t border-separator-border px-5 py-3">
              {footer}
            </footer>
          )}
        </Dialog>
      </AriaModal>
    </ModalOverlay>
  );
}

/** Right-side drawer for details; same behaviour as Modal. */
export function Drawer({ isOpen, onClose, title, description, children, className, ...rest }: OverlayProps) {
  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={(open) => !open && onClose()}
      isDismissable
      className={(state) => cx(scrim(state), 'justify-end')}
    >
      <AriaModal
        className={(state) =>
          cx(
            'flex h-full w-full max-w-180 flex-col border-s border-border-button-default bg-background-secondary-default shadow-xl transition-transform duration-250 ease-out sm:m-2 sm:h-[calc(100%-16px)] sm:rounded-3xl sm:border',
            (state.isEntering || state.isExiting) && 'translate-x-full rtl:-translate-x-full',
            className,
          )
        }
      >
        <Dialog aria-label={rest['aria-label']} className="flex min-h-0 flex-1 flex-col outline-none">
          <Header title={title} description={description} onClose={onClose} />
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </Dialog>
      </AriaModal>
    </ModalOverlay>
  );
}
