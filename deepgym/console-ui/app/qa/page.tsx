import type { Metadata } from 'next';
import { Suspense } from 'react';
import { QAPage } from '@/components/qa/qa-page';

export const metadata: Metadata = { title: 'QA - DeepGym Console' };

export default function Page() {
  return (
    <Suspense>
      <QAPage />
    </Suspense>
  );
}
