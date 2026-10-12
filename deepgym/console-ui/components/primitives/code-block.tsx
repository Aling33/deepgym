'use client';
// Adapted from Beautiful UI "Code Block" (https://beautifului.dev), MIT. See ./LICENSE.
// Changes: data-driven, Python-aware highlighting, BoardUI tokens, Remix icons.

import { RiCheckLine, RiCodeSSlashLine, RiFileCopyLine } from '@remixicon/react';
import { type ReactNode, useState } from 'react';
import type { DiffLine } from '@/lib/line-diff';
import { cx } from '@/utils/cx';

const KEYWORDS = new Set(
  (
    'and as assert async await break class continue def del elif else except finally for from if import in ' +
    'is lambda not or pass raise return try while with yield None True False self const let function export'
  ).split(' '),
);
const TOKEN =
  /(#.*$|"""|'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|[A-Za-z_][\w]*(?=\s*\()|[A-Za-z_][\w]*)/g;

/** Light syntax colouring: comments, strings and numbers, keywords, calls. */
function highlight(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const token = match[0];
    const index = match.index ?? 0;
    let className: string | undefined;
    if (token.startsWith('#')) className = 'text-text-tertiary italic';
    else if (/^["'\d]/.test(token)) className = 'text-status-orange-text';
    else if (KEYWORDS.has(token)) className = 'text-accent-400';
    else if (
      text
        .slice(index + token.length)
        .trimStart()
        .startsWith('(')
    )
      className = 'text-text-primary font-medium';
    if (!className) continue;
    if (index > last) nodes.push(text.slice(last, index));
    nodes.push(
      <span key={index} className={className}>
        {token}
      </span>,
    );
    last = index + token.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

const ROW = 'grid grid-cols-[2.25rem_minmax(0,1fr)] items-start';
const GUTTER = 'select-none pe-2 text-end text-[11px] tabular-nums';

interface CodeBlockProps {
  code: string;
  /** Shown in the header; defaults to a generic label. */
  filename?: string;
  /** Render this unified diff instead of `code` (Copy still copies `code`). */
  diff?: DiffLine[];
  /** Wrap long lines (prose such as task prompts) instead of scrolling. */
  wrap?: boolean;
  /** Skip syntax colouring (plain text such as task prompts). */
  plain?: boolean;
  className?: string;
}

/** Line-numbered source listing (or unified diff) with a copy button. */
export function CodeBlock({ code, filename, diff, wrap, plain, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const lines = code.split('\n');
  const added = diff?.filter((line) => line.type === 'add').length ?? 0;
  const removed = diff?.filter((line) => line.type === 'del').length ?? 0;
  const text = cx('pe-3 ps-1', wrap ? 'whitespace-pre-wrap break-words' : 'whitespace-pre');

  return (
    <div
      className={cx(
        'overflow-hidden rounded-2xl border border-border-button-default bg-background-primary-default shadow-card',
        className,
      )}
    >
      <div className="flex h-10 items-center gap-2 border-b border-separator-border px-3.5 text-body-2-medium">
        <RiCodeSSlashLine aria-hidden className="size-4 shrink-0 text-foreground-icon-secondary" />
        <span className="min-w-0 truncate font-mono text-text-primary">{filename ?? 'source'}</span>
        {diff && (
          <span className="ms-2 inline-flex gap-2 font-mono text-caption-1-medium tabular-nums">
            <span className="text-status-lime-text">+{added}</span>
            <span className="text-status-rose-text">-{removed}</span>
          </span>
        )}
        <button
          type="button"
          onClick={copy}
          aria-label="Copy code"
          className={cx(
            'ms-auto -me-1.5 flex h-6 cursor-pointer items-center gap-1 rounded-md px-1.5 text-caption-1-medium outline-none transition-colors hover:bg-background-secondary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring',
            copied ? 'text-status-lime-text' : 'text-text-tertiary hover:text-text-primary',
          )}
        >
          {copied ? (
            <RiCheckLine aria-hidden className="size-3.5" />
          ) : (
            <RiFileCopyLine aria-hidden className="size-3.5" />
          )}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="scrollbar-thin relative overflow-x-auto py-2.5 font-mono text-[12.5px] leading-[1.65] text-text-secondary">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 start-9 w-px bg-separator-border"
        />
        {diff
          ? diff.map((line, index) => (
              <div
                key={index}
                className={cx(
                  ROW,
                  'relative w-max min-w-full',
                  line.type === 'add' && 'bg-status-lime-background',
                  line.type === 'del' && 'bg-status-rose-background',
                )}
              >
                {line.type !== 'ctx' && (
                  <span
                    aria-hidden
                    className={cx(
                      'absolute inset-y-0 start-0 w-[3px]',
                      line.type === 'add' ? 'bg-status-lime-text' : 'bg-status-rose-text',
                    )}
                  />
                )}
                <span
                  className={cx(
                    GUTTER,
                    line.type === 'add' && 'text-status-lime-text',
                    line.type === 'del' && 'text-status-rose-text',
                    line.type === 'ctx' && 'text-text-tertiary',
                  )}
                >
                  {line.type === 'del' ? line.old : line.cur}
                </span>
                <code className={text}>{plain ? line.text : highlight(line.text)}</code>
              </div>
            ))
          : lines.map((line, index) => (
              <div key={index} className={cx(ROW, !wrap && 'w-max min-w-full')}>
                <span className={cx(GUTTER, 'text-text-tertiary')}>{index + 1}</span>
                <code className={text}>{plain ? line : highlight(line)}</code>
              </div>
            ))}
      </div>
    </div>
  );
}
