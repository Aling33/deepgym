import { Chip } from '@/components/base/badges/chip';
import type { QAReport } from '@/lib/types';

/** pass, fail or skip (environments `deepgym qa` can't check carry one "skipped" check). */
export function qaStatus(report: QAReport): 'pass' | 'fail' | 'skip' {
  if (report.checks.some((check) => check.name === 'skipped')) return 'skip';
  return report.passed ? 'pass' : 'fail';
}

const COLORS = { pass: 'lime', fail: 'rose', skip: 'neutral' } as const;

/** Chip for a report's verdict. */
export function QAStatusBadge({ report }: { report: QAReport }) {
  const status = qaStatus(report);
  return (
    <Chip variant="caption" color={COLORS[status]}>
      {status}
    </Chip>
  );
}
