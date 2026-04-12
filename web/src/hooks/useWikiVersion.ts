import { useState, useEffect } from "react";
import { api, ApiError } from "@/lib/api";
import type { WikiVersionResponse } from "@/lib/types";

export function useWikiVersion(
  channelId: string | undefined,
  versionNumber: number | undefined,
) {
  const [data, setData] = useState<WikiVersionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!channelId || versionNumber == null) {
      setData(null);
      return;
    }

    setIsLoading(true);

    api
      .get<WikiVersionResponse>(
        `/api/channels/${channelId}/wiki/versions/${versionNumber}`,
      )
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
  }, [channelId, versionNumber]);

  return { data, isLoading, error };
}
