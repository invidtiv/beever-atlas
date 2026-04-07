import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export function useWikiRefresh(channelId: string | undefined) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const mutate = useCallback(async () => {
    if (!channelId) return;
    setIsPending(true);
    setError(null);
    try {
      await api.post(`/api/channels/${channelId}/wiki/refresh`);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsPending(false);
    }
  }, [channelId]);

  return { mutate, isPending, error };
}
