'use client';

import { RiCloudLine, RiRefreshLine } from '@remixicon/react';
import { useState } from 'react';
import { Chip } from '@/components/base/badges/chip';
import { Button } from '@/components/base/buttons/button';
import { Card } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/page-header';
import { api, useApi } from '@/lib/api';
import type { ProviderSandboxes, RunningSandbox } from '@/lib/types';
import { KillDialog } from './kill-dialog';
import { SandboxTable } from './sandbox-table';

export interface KillTarget {
  provider: ProviderSandboxes['provider'];
  sandbox: RunningSandbox;
}

const PROVIDER_NAMES: Record<ProviderSandboxes['provider'], string> = {
  apple: 'Apple container',
  docker: 'Docker',
};

/** Live DeepGym sandboxes per local container CLI, refreshed every few seconds, with kill. */
export function SandboxesPage() {
  const { data, error, reload, loading } = useApi<ProviderSandboxes[]>('/sandboxes', 5000);
  const [target, setTarget] = useState<KillTarget | null>(null);

  const kill = async ({ provider, sandbox }: KillTarget) => {
    await api(`/sandboxes/${provider}/${sandbox.id}`, { method: 'DELETE' });
    await reload();
  };

  return (
    <>
      <PageHeader
        title="Sandboxes"
        description="Containers DeepGym started on this machine (named deepgym-*)."
        actions={
          <Button
            size="small"
            variant="secondary"
            leadingIcon={RiRefreshLine}
            disabled={loading}
            onClick={() => void reload()}
          >
            Refresh
          </Button>
        }
      />
      {error && <p className="mb-4 text-body-regular text-text-error-primary">{error}</p>}
      <div className="flex flex-col gap-4">
        {(data ?? []).map((group) => (
          <Card
            key={group.provider}
            flush
            title={PROVIDER_NAMES[group.provider]}
            actions={
              group.available ? (
                <Chip variant="caption" color="lime">
                  {group.sandboxes.length} live
                </Chip>
              ) : (
                <Chip variant="caption" color="neutral">
                  unavailable
                </Chip>
              )
            }
          >
            {group.available ? (
              <SandboxTable
                sandboxes={group.sandboxes}
                onKill={(sandbox) => setTarget({ provider: group.provider, sandbox })}
              />
            ) : (
              <p className="px-4 pb-4 font-mono text-caption-1-medium break-words text-text-tertiary">
                {group.error}
              </p>
            )}
          </Card>
        ))}
        <div className="flex items-start gap-3 rounded-2xl border border-dashed border-border-button-default px-4 py-3">
          <RiCloudLine aria-hidden className="mt-0.5 size-4 shrink-0 text-foreground-icon-secondary" />
          <p className="text-body-2-regular text-text-secondary">
            Cloud sandboxes (Daytona, Modal, E2B) are not listed here. Use each provider&apos;s dashboard;
            DeepGym deletes them when a run or session ends.
          </p>
        </div>
      </div>
      <KillDialog target={target} onClose={() => setTarget(null)} onConfirm={kill} />
    </>
  );
}
