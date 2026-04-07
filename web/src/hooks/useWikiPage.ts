import { useState, useEffect } from "react";
import { api, ApiError } from "@/lib/api";
import type { WikiPage } from "@/lib/types";

export function useWikiPage(channelId: string | undefined, pageId: string | undefined) {
  const [data, setData] = useState<WikiPage | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!channelId || !pageId) {
      setData(null);
      return;
    }

    setIsLoading(true);

    api
      .get<WikiPage>(`/api/channels/${channelId}/wiki/pages/${pageId}`)
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
  }, [channelId, pageId]);

  return { data, isLoading, error };
}
