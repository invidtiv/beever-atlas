import { useState, useEffect, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import type { TopicCluster, MemoryTier1 } from "@/lib/types";

export function useTopics(channelId: string) {
  const [clusters, setClusters] = useState<MemoryTier1[]>([]);
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
      .get<TopicCluster[]>(`/api/channels/${channelId}/topics`)
      .then((res) => {
        const mapped: MemoryTier1[] = res.map((c) => ({
          id: c.id,
          topic: c.summary || "Untitled topic",
          summary: c.summary,
          fact_count: c.member_count,
          date_range: { start: "", end: "" },
          topic_tags: c.topic_tags,
        }));
        setClusters(mapped);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) {
          setClusters([]);
          setError(null);
        } else {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .finally(() => setIsLoading(false));
  }, [channelId, fetchKey]);

  return { clusters, isLoading, error, refetch };
}
