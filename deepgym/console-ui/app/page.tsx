import { Suspense } from 'react';
import { EnvironmentsPage } from '@/components/environments/environments-page';

export default function Page() {
  return (
    <Suspense>
      <EnvironmentsPage />
    </Suspense>
  );
}
