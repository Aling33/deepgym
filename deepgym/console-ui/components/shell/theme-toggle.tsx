'use client';

import { RiMoonLine, RiSunLine } from '@remixicon/react';
import { useTheme } from 'next-themes';
import { IconButton } from '@/components/base/buttons/icon-button';

/** Switch between the dark (default) and light themes. */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme !== 'light';
  return (
    <IconButton
      size="small"
      icon={dark ? RiSunLine : RiMoonLine}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={dark ? 'Light theme' : 'Dark theme'}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
    />
  );
}
