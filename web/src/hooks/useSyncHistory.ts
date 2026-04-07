import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { SyncHistoryEntry } from "@/lib/types";

export function useSyncHistory(channelId: string) {
  const [entries, setEntries] = useState<SyncHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!channelId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<SyncHistoryEntry[]>(
        `/api/channels/${channelId}/sync/history?limit=20`,
      );
      setEntries(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sync history");
    } finally {
      setLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { entries, loading, error, refresh };
}
