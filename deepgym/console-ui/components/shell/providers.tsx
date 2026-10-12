'use client';

import { useRouter } from 'next/navigation';
import { ThemeProvider } from 'next-themes';
import type { ReactNode } from 'react';
import { RouterProvider } from 'react-aria-components';
import { DirectionProvider } from '@/components/foundations/direction/direction';

/** Theme (dark by default), LTR direction, and client-side navigation for react-aria links. */
export function Providers({ children }: { children: ReactNode }) {
  const router = useRouter();
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
      <DirectionProvider locale="en-US">
        <RouterProvider navigate={router.push}>{children}</RouterProvider>
      </DirectionProvider>
    </ThemeProvider>
  );
}
