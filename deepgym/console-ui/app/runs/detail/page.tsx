import type { Metadata } from 'next';
import { Suspense } from 'react';
import { RunDetailPage } from '@/components/runs/run-detail-page';

export const metadata: Metadata = { title: 'Run - DeepGym Console' };

export default function Page() {
  return (
    <Suspense>
      <RunDetailPage />
    </Suspense>
  );
}
