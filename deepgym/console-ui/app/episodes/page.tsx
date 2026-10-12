import type { Metadata } from 'next';
import { Suspense } from 'react';
import { EpisodesPage } from '@/components/episodes/episodes-page';

export const metadata: Metadata = { title: 'Episodes - DeepGym Console' };

export default function Page() {
  return (
    <Suspense>
      <EpisodesPage />
    </Suspense>
  );
}
