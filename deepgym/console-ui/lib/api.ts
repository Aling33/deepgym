'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** FastAPI's `detail` message for a failed response. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: { detail?: unknown } = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item) => item.msg ?? String(item)).join('; ');
  } catch {
    // Not JSON: fall back to the status text below.
  }
  return response.statusText || `HTTP ${response.status}`;
}

/** Call `/api{path}`; JSON in, JSON out. Throws an Error with the API's message on a non-2xx response. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init.body ? { 'Content-Type': 'application/json', ...init.headers } : init.headers,
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Message of anything thrown, for showing next to the action that failed. */
export const errorText = (caught: unknown): string =>
  caught instanceof Error ? caught.message : String(caught);

/** URL path for an environment id, keeping its slashes (e.g. "cyber/web_path_traversal_toy"). */
export const envPath = (id: string): string => id.split('/').map(encodeURIComponent).join('/');

interface ApiState<T> {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
  reload: () => Promise<void>;
}

/**
 * Fetch `path` (skipped while null) and refetch every `intervalMs` if given,
 * for as long as `keepPolling(data)` holds. Responses for a path the
 * component has since moved off are dropped.
 */
export function useApi<T>(
  path: string | null,
  intervalMs?: number,
  keepPolling?: (data: T) => boolean,
): ApiState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(path !== null);
  const current = useRef(path);
  current.current = path;
  const latest = useRef({ data, keepPolling });
  latest.current = { data, keepPolling };

  const reload = useCallback(async () => {
    if (path === null) return;
    try {
      const next = await api<T>(path);
      if (current.current !== path) return;
      setData(next);
      setError(undefined);
    } catch (caught) {
      if (current.current === path) setError(errorText(caught));
    } finally {
      if (current.current === path) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    if (path === null) return;
    setLoading(true);
    void reload();
    if (!intervalMs) return;
    const timer = setInterval(() => {
      const { data: last, keepPolling: shouldPoll } = latest.current;
      if (last === undefined || !shouldPoll || shouldPoll(last)) void reload();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [path, intervalMs, reload]);

  return { data, error, loading, reload };
}
