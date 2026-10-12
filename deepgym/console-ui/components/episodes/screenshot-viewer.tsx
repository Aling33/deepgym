'use client';

import { RiImageLine } from '@remixicon/react';
import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import type { Frame } from '@/lib/types';
import { actionPoint } from './describe-action';

/** The frame's screenshot, cross-faded between steps, with a marker where the next action points. */
export function ScreenshotViewer({ episodeId, frame }: { episodeId: string; frame: Frame }) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
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
    <div className="relative w-full overflow-hidden rounded-2xl border border-border-button-default bg-background-secondary-default">
      <AnimatePresence initial={false} mode="popLayout">
        {/* biome-ignore lint/performance/noImgElement: static export serves API screenshots as-is; next/image can't optimise them. */}
        <motion.img
          key={frame.index}
          src={`/api/episodes/${episodeId}/frames/${frame.index}/screenshot`}
          alt={`Screen at step ${frame.index}`}
          onLoad={(event) =>
            setSize({ w: event.currentTarget.naturalWidth, h: event.currentTarget.naturalHeight })
          }
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="block h-auto w-full"
        />
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
