import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { MemoryTier2 } from "@/lib/types";

interface EntityFactsResponse {
  memories: MemoryTier2[];
  total: number;
}

interface UseEntityFactsReturn {
  facts: MemoryTier2[];
  total: number;
  loading: boolean;
  error: string | null;
}

export function useEntityFacts(
  channelId: string,
  entityName: string | null,
  enabled: boolean,
): UseEntityFactsReturn {
  const [facts, setFacts] = useState<MemoryTier2[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!channelId || !entityName || !enabled) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ entity: entityName, limit: "20" });
      const res = await api.get<EntityFactsResponse>(
        `/api/channels/${channelId}/memories?${params.toString()}`,
      );
      setFacts(res.memories ?? []);
      setTotal(res.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load facts");
      setFacts([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [channelId, entityName, enabled]);

  useEffect(() => {
    if (enabled) {
      fetch();
    } else {
      setFacts([]);
      setTotal(0);
    }
  }, [fetch, enabled]);

  return { facts, total, loading, error };
}
