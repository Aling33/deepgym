import type { NextConfig } from 'next';
import { PHASE_DEVELOPMENT_SERVER } from 'next/constants';

/**
 * Production builds are a static export that `deepgym console` serves from
 * src/deepgym/console/static. `bun run dev` instead proxies /api to a running
 * console (DEEPGYM_CONSOLE_URL, default http://127.0.0.1:8080), since static
 * exports can't rewrite. Dev pages don't get the console's token, so share one:
 *   DEEPGYM_CONSOLE_TOKEN=dev deepgym console        # API
 *   NEXT_PUBLIC_DEEPGYM_TOKEN=dev bun run dev        # UI with hot reload
 */
export default function nextConfig(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    const origin = process.env.DEEPGYM_CONSOLE_URL ?? 'http://127.0.0.1:8080';
    return {
      rewrites: async () => [{ source: '/api/:path*', destination: `${origin}/api/:path*` }],
    };
  }
  return {
    output: 'export',
    trailingSlash: true,
    images: { unoptimized: true },
    experimental: { optimizePackageImports: ['@remixicon/react', 'react-aria-components'] },
  };
}
