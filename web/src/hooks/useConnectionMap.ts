import { useMemo } from "react";
import { useConnections } from "./useConnections";
import type { PlatformConnection } from "@/lib/types";

export interface UseConnectionMapReturn {
  connectionMap: Map<string, PlatformConnection>;
  connections: PlatformConnection[];
  loading: boolean;
  error: string | null;
  getWorkspaceName: (connectionId: string | null) => string;
  refetch: () => void;
}

export function useConnectionMap(): UseConnectionMapReturn {
  const { connections, loading, error, refetch } = useConnections();

  const connectionMap = useMemo(() => {
    const map = new Map<string, PlatformConnection>();
    for (const conn of connections) {
      map.set(conn.id, conn);
    }
    return map;
  }, [connections]);

  const getWorkspaceName = (connectionId: string | null): string => {
    if (!connectionId) return "Ungrouped";
    return connectionMap.get(connectionId)?.display_name ?? "Unknown";
  };

  return { connectionMap, connections, loading, error, getWorkspaceName, refetch };
}
