import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Loader2, Network } from "lucide-react";
import { useGraph } from "@/hooks/useGraph";
import { GraphFilters } from "./GraphFilters";
import { GraphCanvas } from "./GraphCanvas";
import { EntityPanel } from "./EntityPanel";
import { MediaModal } from "./MediaModal";

const MEDIA_TYPES = new Set(["Link", "Document", "Image", "Media"]);

export function GraphTab() {
  const { id: channelId } = useParams<{ id: string }>();
  const { entities, relationships, loading, error } = useGraph(channelId ?? "");
  const [visibleTypes, setVisibleTypes] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mediaModal, setMediaModal] = useState<{ name: string; url: string; mediaType: string } | null>(null);

  // Derive entity types from data; keep all visible when types change
  const entityTypes = [...new Set(entities.map((e) => e.type))].sort();

  useEffect(() => {
    setVisibleTypes(entityTypes);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entities]);

  const selectedEntity = selectedId
    ? entities.find((e) => e.id === selectedId) ?? null
    : null;

  // When a media-type node is selected, open the modal
  const handleSelectEntity = (id: string | null) => {
    if (id) {
      const entity = entities.find((e) => e.id === id);
      if (entity) {
        const props = entity.properties as Record<string, unknown> | undefined;
        const url = (props?.url as string) || "";
        const mediaType = (props?.media_type as string) || entity.type.toLowerCase();
        if (url && (MEDIA_TYPES.has(entity.type) || mediaType)) {
          setMediaModal({ name: entity.name, url, mediaType });
          return;
        }
      }
    }
    setSelectedId(id);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-sm">Loading graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <p className="text-sm text-destructive">{error}</p>
      </div>
    );
  }

  if (entities.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <div className="max-w-sm w-full text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
            <Network className="h-7 w-7 text-primary" />
          </div>
          <h3 className="text-lg font-semibold text-foreground">No entities yet</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Sync this channel to extract entities and build a knowledge graph from its conversations.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <GraphFilters entityTypes={entityTypes} selected={visibleTypes} onChange={setVisibleTypes} />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <GraphCanvas
          entities={entities}
          relationships={relationships}
          visibleTypes={visibleTypes}
          selectedEntityId={selectedId}
          onSelectEntity={handleSelectEntity}
        />
        {selectedEntity && (
          <EntityPanel
            entity={selectedEntity}
            relationships={relationships}
            allEntities={entities}
            channelId={channelId ?? ""}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
      {mediaModal && (
        <MediaModal
          name={mediaModal.name}
          url={mediaModal.url}
          mediaType={mediaModal.mediaType}
          onClose={() => setMediaModal(null)}
        />
      )}
    </div>
  );
}
