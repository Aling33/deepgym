'use client';

import { RiSearchLine, RiStackLine } from '@remixicon/react';
import { useMemo, useRef, useState } from 'react';
import { Input } from '@/components/base/input/input';
import { Kbd } from '@/components/base/kbd/kbd';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { FilterSelect } from '@/components/ui/filter-select';
import { PageHeader } from '@/components/ui/page-header';
import { useApi } from '@/lib/api';
import { matches } from '@/lib/format';
import type { EnvironmentSummary } from '@/lib/types';
import { useHotkey } from '@/lib/use-hotkey';
import { useQueryParam } from '@/lib/use-query-param';
import { EnvDrawer } from './env-drawer';
import { EnvTable } from './env-table';

const distinct = (envs: EnvironmentSummary[], key: 'kind' | 'difficulty' | 'domain') =>
  [...new Set(envs.map((env) => env[key]))].toSorted();

/** Searchable, filterable registry table; the selected environment opens in a drawer (?env=). */
export function EnvironmentsPage() {
  const { data, error } = useApi<EnvironmentSummary[]>('/environments');
  const [query, setQuery] = useState('');
  const [kind, setKind] = useQueryParam('kind');
  const [difficulty, setDifficulty] = useQueryParam('difficulty');
  const [domain, setDomain] = useQueryParam('domain');
  const [selected, setSelected] = useQueryParam('env');
  const search = useRef<HTMLInputElement>(null);
  useHotkey('/', () => search.current?.focus());

  const envs = data ?? [];
  const rows = useMemo(
    () =>
      (data ?? []).filter(
        (env) =>
          (!kind || env.kind === kind) &&
          (!difficulty || env.difficulty === difficulty) &&
          (!domain || env.domain === domain) &&
          matches(query, env.name, env.id, env.family, ...env.tags),
      ),
    [data, kind, difficulty, domain, query],
  );

  return (
    <>
      <PageHeader
        title="Environments"
        description="Tasks with verifiable rewards. Open one to read its task, verifier and reference solution."
      />
      <Card flush>
        <div className="flex flex-wrap items-center gap-2 p-3">
          <div className="relative w-full sm:w-80">
            <Input
              ref={search}
              size="small"
              leadingIcon={RiSearchLine}
              placeholder="Search name, id, family or tag"
              aria-label="Search environments"
              value={query}
              onChange={setQuery}
            />
            <Kbd className="pointer-events-none absolute end-2 top-1/2 hidden -translate-y-1/2 sm:inline-flex">
              /
            </Kbd>
          </div>
          <FilterSelect label="kinds" value={kind} options={distinct(envs, 'kind')} onChange={setKind} />
          <FilterSelect
            label="difficulties"
            value={difficulty}
            options={distinct(envs, 'difficulty')}
            onChange={setDifficulty}
          />
          <FilterSelect
            label="domains"
            value={domain}
            options={distinct(envs, 'domain')}
            onChange={setDomain}
          />
          <span className="ms-auto font-mono text-caption-1-medium text-text-tertiary">
            {rows.length} / {envs.length}
          </span>
        </div>
        {error ? (
          <EmptyState icon={RiStackLine} title="Could not load environments">
            {error}
          </EmptyState>
        ) : (
          <EnvTable rows={rows} loading={!data} onOpen={(env) => setSelected(env.id)} />
        )}
      </Card>
      <EnvDrawer id={selected} onClose={() => setSelected(null)} />
    </>
  );
}
