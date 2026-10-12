'use client';

import { useMemo } from 'react';
import { Tab, TabList, TabPanel, Tabs } from '@/components/base/tabs/tabs';
import { CodeBlock } from '@/components/primitives/code-block';
import { envPath, useApi } from '@/lib/api';
import { lineDiff } from '@/lib/line-diff';
import type { EnvironmentDetail, RunDetail } from '@/lib/types';

/** The scored solution, verifier output and, for custom solutions, a diff against the reference. */
export function RunSource({ run }: { run: RunDetail }) {
  const { data: env } = useApi<EnvironmentDetail>(
    run.reference ? null : `/environments/${envPath(run.environment)}`,
  );
  const diff = useMemo(
    () => (env?.reference ? lineDiff(env.reference, run.solution) : undefined),
    [env?.reference, run.solution],
  );
  const output = [run.result?.output, run.result?.stderr].filter(Boolean).join('\n\n');

  return (
    <Tabs>
      <TabList aria-label="Run source">
        <Tab id="solution">Solution</Tab>
        <Tab id="diff" isDisabled={!diff}>
          Diff vs reference
        </Tab>
        <Tab id="output" isDisabled={!output}>
          Verifier output
        </Tab>
      </TabList>
      <TabPanel id="solution">
        <CodeBlock code={run.solution} filename={run.reference ? 'reference_solution.py' : 'solution.py'} />
      </TabPanel>
      <TabPanel id="diff">
        {diff && (
          <CodeBlock code={run.solution} filename="reference_solution.py -> solution.py" diff={diff} />
        )}
      </TabPanel>
      <TabPanel id="output">
        <CodeBlock code={output} filename="verifier output" wrap plain />
      </TabPanel>
    </Tabs>
  );
}
