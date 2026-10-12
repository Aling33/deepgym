'use client';

import { RiDeleteBinLine } from '@remixicon/react';
import { useState } from 'react';
import { Button } from '@/components/base/buttons/button';
import { Modal } from '@/components/ui/overlay';
import { errorText } from '@/lib/api';
import type { KillTarget } from './sandboxes-page';

interface KillDialogProps {
  target: KillTarget | null;
  onClose: () => void;
  onConfirm: (target: KillTarget) => Promise<void>;
}

/** Confirm before force-removing a sandbox; shows the CLI's error if removal fails. */
export function KillDialog({ target, onClose, onConfirm }: KillDialogProps) {
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    if (!target) return;
    setBusy(true);
    setError(undefined);
    try {
      await onConfirm(target);
      onClose();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      isOpen={target !== null}
      onClose={onClose}
      title="Kill sandbox"
      className="max-w-md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" leadingIcon={RiDeleteBinLine} disabled={busy} onClick={confirm}>
            Kill
          </Button>
        </>
      }
    >
      <p className="text-body-regular text-text-secondary">
        Force-remove <code className="font-mono text-text-primary">{target?.sandbox.id}</code>? Any run or
        session using it fails.
      </p>
      {error && <p className="mt-3 text-body-2-medium text-text-error-primary">{error}</p>}
    </Modal>
  );
}
