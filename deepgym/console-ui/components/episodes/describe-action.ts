import type { Action } from '@/lib/types';

const POINTER = new Set(['click', 'double_click', 'right_click', 'move']);

/** One-line, human-readable form of an agent action ("click (376, 121)", "type \"Pay rent\""). */
export function describeAction(action: Action | null): string {
  if (!action) return 'final observation';
  const { action_type: kind, content, x, y } = action;
  if (POINTER.has(kind)) return `${kind} (${x}, ${y})`;
  switch (kind) {
    case 'drag':
      return `drag (${x}, ${y}) -> (${action.to_x}, ${action.to_y})`;
    case 'type':
      return `type "${content}"`;
    case 'key':
      return `key ${content}`;
    case 'scroll':
      return `scroll ${content} x${action.amount}`;
    case 'wait':
      return `wait ${action.amount}s`;
    case 'write_file':
      return `write ${action.path}`;
    case 'code':
    case 'bash':
      return `${kind}: ${content.split('\n')[0]}`;
    default:
      return kind;
  }
}

/** Screen point an action targets, if it has one. */
export function actionPoint(action: Action | null): { x: number; y: number } | null {
  if (!action || action.x === null || action.y === null) return null;
  return { x: action.x, y: action.y };
}
