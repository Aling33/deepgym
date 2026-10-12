'use client';

import { RiSearchLine } from '@remixicon/react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { type ReactNode, useEffect, useState } from 'react';
import { Kbd } from '@/components/base/kbd/kbd';
import { isActive, NAV, type NavItem } from '@/lib/nav';
import { useHotkey } from '@/lib/use-hotkey';
import { cx } from '@/utils/cx';
import { CommandPalette } from './command-palette';
import { Sidebar } from './sidebar';
import { ThemeToggle } from './theme-toggle';

function NavChord({ item }: { item: NavItem }) {
  const router = useRouter();
  useHotkey(item.chord, () => router.push(item.href));
  return null;
}

/** Page frame: floating sidebar, top bar with ⌘K search and theme toggle, scrolling main area. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="relative flex h-dvh w-full overflow-hidden bg-background-full">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-96 bg-[radial-gradient(55%_100%_at_25%_0%,color-mix(in_srgb,var(--color-accent-400)_7%,transparent),transparent)]"
      />
      {NAV.map((item) => (
        <NavChord key={item.href} item={item} />
      ))}
      <div className="relative hidden w-60 shrink-0 p-3 pr-0 md:block">
        <Sidebar />
      </div>
      <div className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex h-15 shrink-0 items-center gap-3 px-4 md:px-7">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex h-9 w-full max-w-sm cursor-pointer items-center gap-2 rounded-full bg-background-tertiary-default ps-3 pe-2 text-body-regular text-text-tertiary outline-none transition-colors hover:bg-background-tertiary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring"
          >
            <RiSearchLine aria-hidden className="size-4.5 text-foreground-icon-secondary" />
            <span className="flex-1 text-start">Search</span>
            <Kbd>⌘K</Kbd>
          </button>
          <div className="ms-auto">
            <ThemeToggle />
          </div>
        </header>
        <nav
          aria-label="Pages"
          className="scrollbar-thin flex shrink-0 gap-1 overflow-x-auto px-4 pb-2 md:hidden"
        >
          {NAV.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cx(
                  'flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1 text-body-2-medium',
                  active
                    ? 'bg-linear-to-b from-accent-500 to-accent-600 text-text-white'
                    : 'text-text-secondary hover:bg-background-secondary-hover',
                )}
              >
                <item.icon aria-hidden className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1440px] px-4 pt-2 pb-12 md:px-7">{children}</div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
