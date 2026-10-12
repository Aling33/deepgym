'use client';

import { RiHistoryLine, RiPlayLine } from '@remixicon/react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Chip } from '@/components/base/badges/chip';
import { Button } from '@/components/base/buttons/button';
import { Select, SelectItem } from '@/components/base/select/select';
import { Tab, TabList, TabPanel, Tabs } from '@/components/base/tabs/tabs';
import { CodeBlock } from '@/components/primitives/code-block';
import { Drawer } from '@/components/ui/overlay';
import { KindBadge } from '@/components/ui/status-badge';
import { envPath, useApi } from '@/lib/api';
import type { EnvironmentDetail } from '@/lib/types';

function VariantSelect({
  count,
  value,
  onChange,
}: {
  count: number;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <Select
      aria-label="Variant"
      size="sm"
      selectedKey={String(value)}
      onSelectionChange={(key) => onChange(Number(key))}
    >
      {Array.from({ length: count }, (_, index) => (
        <SelectItem key={index} id={String(index)}>
          {`Variant ${index}`}
        </SelectItem>
      ))}
    </Select>
  );
}

function EnvDetailView({ id }: { id: string }) {
  const router = useRouter();
  const [variant, setVariant] = useState(0);
  const { data: env, error } = useApi<EnvironmentDetail>(`/environments/${envPath(id)}?variant=${variant}`);

  if (error) return <p className="text-body-regular text-text-error-primary">{error}</p>;
  if (!env) return <p className="text-body-regular text-text-tertiary">Loading {id}</p>;
  const runnable = env.kind === 'single-turn';

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <KindBadge kind={env.kind} />
        <Chip variant="caption" color="neutral">
          {env.difficulty}
        </Chip>
        <Chip variant="caption" color="neutral">
          {env.domain}
        </Chip>
        {env.family && (
          <Chip variant="caption" color="neutral">
            {env.family}
          </Chip>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {runnable && (
          <Button
            size="small"
            leadingIcon={RiPlayLine}
            onClick={() => router.push(`/runs/?new=${encodeURIComponent(id)}`)}
          >
            New run
          </Button>
        )}
        <Button
          size="small"
          variant="secondary"
          leadingIcon={RiHistoryLine}
          onClick={() => router.push(`/runs/?environment=${encodeURIComponent(id)}`)}
        >
          Runs
        </Button>
        {env.variants > 1 && <VariantSelect count={env.variants} value={variant} onChange={setVariant} />}
      </div>
      {!runnable && (
        <p className="text-body-2-regular text-text-secondary">
          Needs an agent rather than one solution. Store its episodes with{' '}
          <code className="font-mono text-text-primary">deepgym.console.record_episode</code> to replay them
          here.
        </p>
      )}
      <Tabs>
        <TabList aria-label="Environment details">
          <Tab id="task">Task</Tab>
          <Tab id="verifier">Verifier</Tab>
          <Tab id="reference" isDisabled={!env.reference}>
            Reference
          </Tab>
          <Tab id="metadata">Metadata</Tab>
        </TabList>
        <TabPanel id="task">
          <CodeBlock code={env.task} filename="task.md" wrap plain />
        </TabPanel>
        <TabPanel id="verifier">
          <CodeBlock code={env.verifier} filename="verifier.py" />
        </TabPanel>
        <TabPanel id="reference">
          <CodeBlock code={env.reference ?? ''} filename="reference_solution.py" />
        </TabPanel>
        <TabPanel id="metadata">
          <CodeBlock code={JSON.stringify(env.metadata, null, 2)} filename="registry entry" plain />
        </TabPanel>
      </Tabs>
    </div>
  );
}

/** Right-side drawer with one environment's task, verifier, reference and metadata tabs. */
export function EnvDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  // Keep the last id while the drawer animates closed.
  const [shown, setShown] = useState(id);
  if (id !== null && id !== shown) setShown(id);
  return (
    <Drawer
      isOpen={id !== null}
      onClose={onClose}
      aria-label="Environment details"
      title={shown ?? ''}
      description={<span className="font-mono text-caption-1-medium">environment</span>}
    >
      {shown && <EnvDetailView key={shown} id={shown} />}
    </Drawer>
  );
}
