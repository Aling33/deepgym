'use client';

import { useEffect, useRef } from 'react';

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
}

/**
 * Run `handler` when `key` is pressed outside text fields and without modifiers.
 * `key` may be a two-key sequence such as "g r" (second key within a second).
 */
export function useHotkey(key: string, handler: () => void, enabled = true): void {
  const latest = useRef(handler);
  latest.current = handler;

  useEffect(() => {
    if (!enabled) return;
    const [first, second] = key.split(' ');
    let armedAt = 0;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) return;
      if (!second) {
        if (event.key !== first) return;
        event.preventDefault();
        latest.current();
        return;
      }
      if (event.key === first) {
        armedAt = Date.now();
      } else if (event.key === second && Date.now() - armedAt < 1000) {
        armedAt = 0;
        event.preventDefault();
        latest.current();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [key, enabled]);
}
