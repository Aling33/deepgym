'use client';

import { RiImageLine } from '@remixicon/react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import type { Frame } from '@/lib/types';
import { actionPoint } from './describe-action';

/** Object URL of a frame's screenshot, fetched with the console token (an <img src> can't send it). */
function useScreenshot(episodeId: string, frame: Frame): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!frame.has_screenshot) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    void (async () => {
      const response = await apiFetch(`/episodes/${episodeId}/frames/${frame.index}/screenshot`);
      const blob = await response.blob();
      if (cancelled) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [episodeId, frame.index, frame.has_screenshot]);
  return frame.has_screenshot ? url : null;
}

/** The frame's screenshot, cross-faded between steps, with a marker where the next action points. */
export function ScreenshotViewer({ episodeId, frame }: { episodeId: string; frame: Frame }) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const url = useScreenshot(episodeId, frame);
  const point = actionPoint(frame.action);

  if (!frame.has_screenshot) {
    return (
      <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border-button-default text-body-2-regular text-text-tertiary">
        <RiImageLine aria-hidden className="size-5" />
        No screenshot at this step
      </div>
    );
  }

  return (
    <div
      className="relative w-full overflow-hidden rounded-2xl border border-border-button-default bg-background-secondary-default"
      style={{ aspectRatio: size ? `${size.w} / ${size.h}` : '4 / 3' }}
    >
      <AnimatePresence initial={false} mode="popLayout">
        {url && (
          // biome-ignore lint/performance/noImgElement: static export shows API screenshots as-is; next/image can't optimise them.
          <motion.img
            key={url}
            src={url}
            alt={`Screen at step ${frame.index}`}
            onLoad={(event) =>
              setSize({ w: event.currentTarget.naturalWidth, h: event.currentTarget.naturalHeight })
            }
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="absolute inset-0 block h-full w-full"
          />
        )}
      </AnimatePresence>
      {point && size && (
        <span
          aria-hidden
          className="pointer-events-none absolute size-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent-400 bg-accent-400/20 shadow-[0_0_0_4px_color-mix(in_srgb,var(--color-accent-400)_25%,transparent)]"
          style={{ left: `${(point.x / size.w) * 100}%`, top: `${(point.y / size.h) * 100}%` }}
        />
      )}
    </div>
  );
}
