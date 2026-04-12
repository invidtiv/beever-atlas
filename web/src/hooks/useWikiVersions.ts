import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { WikiVersionSummary } from "@/lib/types";

export function useWikiVersions(channelId: string | undefined) {
  const [data, setData] = useState<WikiVersionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    if (!channelId) {
      setData([]);
      return;
    }

    setIsLoading(true);

    api
      .get<WikiVersionSummary[]>(`/api/channels/${channelId}/wiki/versions`)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => setIsLoading(false));
  }, [channelId, fetchKey]);

  return { data, isLoading, error, refetch };
}
