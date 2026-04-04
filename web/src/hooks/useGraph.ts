import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

export interface GraphEntity {
  id: string;
  name: string;
  type: "Person" | "Decision" | "Project" | "Technology" | string;
  scope?: string;
  properties?: Record<string, unknown>;
  aliases?: string[];
  status?: "active" | "pending" | string;
}

export interface GraphRelationship {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
}

interface UseGraphReturn {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

interface MediaNode {
  id: string;
  url: string;
  media_type: string;
  title: string;
}

export function useGraph(channelId: string): UseGraphReturn {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!channelId) return;
    setLoading(true);
    setError(null);
    try {
      // Fetch entities, relationships, and media nodes in parallel.
      const [entityData, relData, mediaData] = await Promise.all([
        api.get<GraphEntity[]>(`/api/graph/entities?channel_id=${channelId}`),
        api.get<{ source: string; target: string; type: string; id?: string }[]>(
          `/api/graph/relationships?channel_id=${channelId}`,
        ),
        api.get<MediaNode[]>(`/api/graph/media?channel_id=${channelId}`),
      ]);
      const baseEntities = Array.isArray(entityData) ? entityData : [];

      // Convert Media nodes to GraphEntity format for unified rendering.
      // Deduplicate: skip Media nodes whose name closely matches an existing Entity.
      const entityNames = new Set(baseEntities.map((e) => e.name.toLowerCase().replace(/[\s_-]+/g, "")));
      const mediaEntities: GraphEntity[] = (Array.isArray(mediaData) ? mediaData : [])
        .map((m) => {
          let name: string;
          try {
            name = m.title || (m.media_type === "link" ? new URL(m.url).hostname : m.url.split("/").pop() || m.url);
          } catch {
            name = m.url.split("/").pop() || m.url;
          }
          return {
            id: m.id,
            name,
            type: m.media_type === "link" ? "Link" : m.media_type === "pdf" ? "Document" : m.media_type === "image" ? "Image" : "Media",
            scope: "channel",
            properties: { url: m.url, media_type: m.media_type },
          };
        })
        .filter((m) => !entityNames.has(m.name.toLowerCase().replace(/[\s_-]+/g, "")));

      const entities = [...baseEntities, ...mediaEntities];
      setEntities(entities);

      // Map relationship source/target names to entity IDs for cytoscape edges.
      const nameToId = new Map(entities.map((e) => [e.name, e.id]));
      const rels: GraphRelationship[] = (Array.isArray(relData) ? relData : [])
        .map((r, i) => ({
          id: r.id ?? `rel-${i}`,
          source_id: nameToId.get(r.source) ?? "",
          target_id: nameToId.get(r.target) ?? "",
          type: r.type,
        }))
        .filter((r) => r.source_id && r.target_id);
      setRelationships(rels);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { entities, relationships, loading, error, refetch: fetch };
}

export interface Subgraph {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
}

interface UseEntityNeighborsReturn {
  subgraph: Subgraph | null;
  loading: boolean;
}

export function useEntityNeighbors(
  entityId: string | null,
): UseEntityNeighborsReturn {
  const [subgraph, setSubgraph] = useState<Subgraph | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entityId) {
      setSubgraph(null);
      return;
    }
    setLoading(true);
    api
      .get<Subgraph>(`/api/graph/entities/${entityId}/neighbors`)
      .then(setSubgraph)
      .catch(() => setSubgraph(null))
      .finally(() => setLoading(false));
  }, [entityId]);

  return { subgraph, loading };
}
