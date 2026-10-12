import type { Metadata } from 'next';
import { Suspense } from 'react';
import { RunsPage } from '@/components/runs/runs-page';

export const metadata: Metadata = { title: 'Runs - DeepGym Console' };

export default function Page() {
  return (
    <Suspense>
      <RunsPage />
    </Suspense>
  );
}
