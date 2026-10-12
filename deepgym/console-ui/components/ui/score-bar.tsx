import { formatScore } from '@/lib/format';
import { cx } from '@/utils/cx';

/** Score in [0, 1] as a thin bar plus its value; a dash while unknown. */
export function ScoreBar({ score, className }: { score: number | null; className?: string }) {
  if (score === null) return <span className="font-mono text-caption-1-medium text-text-tertiary">-</span>;
  const percent = Math.round(score * 100);
  return (
    <div className={cx('flex items-center gap-2', className)}>
      <div aria-hidden className="h-1.5 w-16 overflow-hidden rounded-full bg-background-tertiary-default">
        <div
          className={cx('h-full rounded-full', score >= 1 ? 'bg-status-lime-text' : 'bg-accent-400')}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="w-9 font-mono text-caption-1-medium text-text-primary tabular-nums">
        {formatScore(score)}
      </span>
    </div>
  );
}
