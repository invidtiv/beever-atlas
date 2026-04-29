/**
 * Shared <img> wrapper that resolves a proxied URL via mintLoaderUrl
 * (issue #89) and gracefully handles load failures.
 *
 * Why this component exists:
 *   `mintLoaderUrl` is async, but `<img src>` needs a string. Every image
 *   callsite in the app would otherwise need to duplicate useState +
 *   useEffect + onError-retry boilerplate. Centralizing it here keeps
 *   the 9 callsites uniform and ensures the bounded-retry contract is
 *   consistent everywhere.
 *
 * onError behavior (bounded at 2 attempts):
 *   1. First load fails:    re-mint with `forceRefresh: true` (covers
 *                           expired-cache, rotated-secret, and stale-token
 *                           cases) and swap `src`.
 *   2. Second load fails:   fall back to `unproxiedUrl` and stop. We do
 *                           NOT loop — `<img>` cannot read HTTP status
 *                           codes from JS, so distinguishing 401 from
 *                           404/network/CORS is impossible. A bounded
 *                           retry is the only safe contract.
 */

import { useEffect, useRef, useState } from "react";
import type { ImgHTMLAttributes } from "react";

import { mintLoaderUrl } from "@/lib/api";

export interface ProxiedImageProps
  extends Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> {
  /**
   * The original, unproxied URL. Used as the placeholder while the proxy
   * URL resolves and as the final fallback after both retry attempts.
   */
  unproxiedUrl: string;
  /**
   * The proxy path to mint a token for, e.g.
   * `/api/files/proxy?url=<encoded-url>`. The mint helper will derive the
   * route path (`/api/files/proxy`) for the token's path-prefix binding.
   */
  mediaPath: string;
}

export function ProxiedImage({
  unproxiedUrl,
  mediaPath,
  onError: callerOnError,
  ...imgProps
}: ProxiedImageProps) {
  const [src, setSrc] = useState<string | undefined>(undefined);
  const retriedRef = useRef(false);
  const fallbackRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    retriedRef.current = false;
    fallbackRef.current = false;
    mintLoaderUrl(mediaPath).then((resolved) => {
      if (!cancelled) setSrc(resolved);
    });
    return () => {
      cancelled = true;
    };
  }, [mediaPath]);

  const handleError = (event: React.SyntheticEvent<HTMLImageElement, Event>) => {
    // If we've already exhausted retries and fallen back to unproxiedUrl,
    // forward the error to the caller (they may want to render a
    // placeholder) but do nothing else.
    if (fallbackRef.current) {
      callerOnError?.(event);
      return;
    }

    if (!retriedRef.current) {
      retriedRef.current = true;
      // First failure: cache-busting remint to recover from expired or
      // rotated tokens.
      mintLoaderUrl(mediaPath, { forceRefresh: true })
        .then((resolved) => setSrc(resolved))
        .catch(() => {
          // Mint endpoint itself failed even with forceRefresh — fall
          // back to unproxied URL.
          fallbackRef.current = true;
          setSrc(unproxiedUrl);
        });
      return;
    }

    // Second failure: fall back to unproxied URL and stop retrying.
    fallbackRef.current = true;
    setSrc(unproxiedUrl);
    callerOnError?.(event);
  };

  return (
    <img
      src={src ?? unproxiedUrl}
      onError={handleError}
      {...imgProps}
    />
  );
}
