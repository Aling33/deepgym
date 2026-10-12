import { Chip, type ChipProps } from '@/components/base/badges/chip';
import type { EnvKind, RunStatus } from '@/lib/types';
import { cx } from '@/utils/cx';

type ChipColor = NonNullable<ChipProps['color']>;

const RUN_STATUS: Record<RunStatus, { color: ChipColor; dot: string; pulse?: boolean }> = {
  queued: { color: 'neutral', dot: 'bg-foreground-icon-secondary' },
  running: { color: 'blue', dot: 'bg-accent-400', pulse: true },
  completed: { color: 'lime', dot: 'bg-status-lime-text' },
  failed: { color: 'rose', dot: 'bg-status-rose-text' },
};

/** Pill for a run's lifecycle status, with a pulsing dot while it runs. */
export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { color, dot, pulse } = RUN_STATUS[status];
  return (
    <Chip variant="caption" color={color} className="gap-1.5">
      <span aria-hidden className={cx('size-1.5 rounded-full', dot, pulse && 'animate-pulse')} />
      {status}
    </Chip>
  );
}

/** Pass/fail pill; a dash while unknown. */
export function PassBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) return <span className="text-text-tertiary">-</span>;
  return (
    <Chip variant="caption" color={passed ? 'lime' : 'rose'}>
      {passed ? 'pass' : 'fail'}
    </Chip>
  );
}

const KIND_COLOR: Record<EnvKind, ChipColor> = {
  'single-turn': 'neutral',
  'multi-turn': 'cyan',
  'computer-use': 'blue',
};

/** Chip for an environment's interaction kind. */
export function KindBadge({ kind }: { kind: EnvKind }) {
  return (
    <Chip variant="caption" color={KIND_COLOR[kind]}>
      {kind}
    </Chip>
  );
}
