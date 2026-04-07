import { useState, useEffect, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import type { WikiResponse } from "@/lib/types";

export function useWiki(channelId: string | undefined) {
  const [data, setData] = useState<WikiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    if (!channelId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    api
      .get<WikiResponse>(`/api/channels/${channelId}/wiki`)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setData(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .finally(() => setIsLoading(false));
  }, [channelId, fetchKey]);

  return { data, isLoading, error, refetch };
}
