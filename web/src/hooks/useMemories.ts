import { useState, useMemo } from "react";
import type { MemoryTier0, MemoryTier1, MemoryTier2 } from "@/lib/types";
import { mockSummary, mockClusters, mockFacts } from "@/lib/mock-memories";

export interface MemoryFilters {
  topic: string;
  entity: string;
  minImportance: string;
  dateFrom: string;
  dateTo: string;
}

const defaultFilters: MemoryFilters = {
  topic: "",
  entity: "",
  minImportance: "",
  dateFrom: "",
  dateTo: "",
};

export function useMemories(_channelId: string) {
  const [filters, setFilters] = useState<MemoryFilters>(defaultFilters);
  const isLoading = false;

  const summary: MemoryTier0 = mockSummary;
  const clusters: MemoryTier1[] = mockClusters;

  const facts: MemoryTier2[] = useMemo(() => {
    let filtered = [...mockFacts];

    if (filters.topic) {
      filtered = filtered.filter((f) =>
        f.topic_tags.some((t) =>
          t.toLowerCase().includes(filters.topic.toLowerCase()),
        ),
      );
    }

    if (filters.entity) {
      filtered = filtered.filter((f) =>
        f.entity_tags.some((e) =>
          e.toLowerCase().includes(filters.entity.toLowerCase()),
        ),
      );
    }

    if (filters.minImportance) {
      const levels = ["low", "medium", "high", "critical"];
      const minIdx = levels.indexOf(filters.minImportance);
      filtered = filtered.filter(
        (f) => levels.indexOf(f.importance) >= minIdx,
      );
    }

    return filtered;
  }, [filters]);

  return { summary, clusters, facts, filters, setFilters, isLoading };
}
