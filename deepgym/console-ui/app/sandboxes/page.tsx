import type { Metadata } from 'next';
import { SandboxesPage } from '@/components/sandboxes/sandboxes-page';

export const metadata: Metadata = { title: 'Sandboxes - DeepGym Console' };

export default function Page() {
  return <SandboxesPage />;
}
