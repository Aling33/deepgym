'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

/** Read and replace one URL query parameter, so drawers and filters are deep-linkable. */
export function useQueryParam(name: string): [string | null, (value: string | null) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const set = useCallback(
    (value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value === null || value === '') next.delete(name);
      else next.set(name, value);
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [name, params, pathname, router],
  );

  return [params.get(name), set];
}
