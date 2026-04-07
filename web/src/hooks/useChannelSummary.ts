import { useState, useEffect, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import type { MemoryTier0, ChannelSummaryResponse } from "@/lib/types";

export function useChannelSummary(channelId: string) {
  const [summary, setSummary] = useState<MemoryTier0 | null>(null);
  const [clusterCount, setClusterCount] = useState(0);
  const [factCount, setFactCount] = useState(0);
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
      .get<ChannelSummaryResponse>(`/api/channels/${channelId}/summary`)
      .then((res) => {
        setSummary({
          channel_id: channelId,
          channel_name: channelId, // TODO: resolve channel name from ChannelInfo or route context
          summary: res.text,
          updated_at: "",
          message_count: res.fact_count,
        });
        setClusterCount(res.cluster_count);
        setFactCount(res.fact_count);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setSummary(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .finally(() => setIsLoading(false));
  }, [channelId, fetchKey]);

  return { summary, clusterCount, factCount, isLoading, error, refetch };
}
