import { useState, useEffect } from "react";
import { X } from "lucide-react";
import type { GraphEntity, GraphRelationship } from "@/hooks/useGraph";
import { useEntityFacts } from "@/hooks/useEntityFacts";
import { FactCard } from "@/components/memories/FactCard";
import { cn } from "@/lib/utils";
import { getTypeColors } from "./GraphFilters";

interface EntityPanelProps {
  entity: GraphEntity;
  relationships: GraphRelationship[];
  allEntities: GraphEntity[];
  channelId: string;
  onClose: () => void;
}

export function EntityPanel({
  entity,
  relationships,
  allEntities,
  channelId,
  onClose,
}: EntityPanelProps) {
  const [activeTab, setActiveTab] = useState<"details" | "facts">("details");

  // Reset tab when entity changes
  useEffect(() => {
    setActiveTab("details");
  }, [entity.id]);

  const { facts, total, loading: factsLoading } = useEntityFacts(
    channelId,
    entity.name,
    activeTab === "facts",
  );

  const connected = relationships.filter(
    (r) => r.source_id === entity.id || r.target_id === entity.id,
  );

  function resolveEntityName(id: string): string {
    return allEntities.find((e) => e.id === id)?.name ?? id;
  }

  const properties = entity.properties
    ? Object.entries(entity.properties).filter(([, v]) => v != null)
    : [];

  const aliases = entity.aliases ?? [];

  return (
    <div className="w-full sm:w-96 shrink-0 border-l border-border bg-card flex flex-col overflow-hidden absolute sm:relative inset-0 sm:inset-auto z-10 sm:z-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 px-4 py-3 border-b border-border">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm text-foreground truncate">
            {entity.name}
          </h3>
          <div className="flex items-center gap-1.5 mt-1">
            <span
              className={cn(
                "inline-flex px-2 py-0.5 rounded-md text-xs font-medium",
                getTypeColors(entity.type).pill,
              )}
            >
              {entity.type}
            </span>
            {entity.scope && (
              <span className="text-xs text-muted-foreground truncate">
                {entity.scope}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 w-6 h-6 flex items-center justify-center rounded-md hover:bg-muted transition-colors text-muted-foreground"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setActiveTab("details")}
          className={cn(
            "flex-1 px-3 py-2 text-xs font-medium transition-colors",
            activeTab === "details"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Details
        </button>
        <button
          onClick={() => setActiveTab("facts")}
          className={cn(
            "flex-1 px-3 py-2 text-xs font-medium transition-colors",
            activeTab === "facts"
              ? "text-foreground border-b-2 border-primary"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Facts{total > 0 ? ` (${total})` : ""}
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === "details" && (
          <div className="divide-y divide-border">
            {/* Aliases */}
            {aliases.length > 0 && (
              <section className="px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Aliases
                </p>
                <div className="flex flex-wrap gap-1">
                  {aliases.map((alias) => (
                    <span
                      key={alias}
                      className="px-2 py-0.5 rounded-md bg-muted text-xs text-muted-foreground"
                    >
                      {alias}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Properties */}
            {properties.length > 0 && (
              <section className="px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Properties
                </p>
                <dl className="space-y-1.5">
                  {properties.map(([key, val]) => (
                    <div key={key} className="flex gap-2">
                      <dt className="text-xs text-muted-foreground shrink-0 w-24 truncate capitalize">
                        {key.replace(/_/g, " ")}
                      </dt>
                      <dd className="text-xs text-foreground break-words min-w-0">
                        {String(val)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}

            {/* Relationships */}
            {connected.length > 0 && (
              <section className="px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Relationships ({connected.length})
                </p>
                <ul className="space-y-2">
                  {connected.map((rel) => {
                    const isSource = rel.source_id === entity.id;
                    const otherId = isSource ? rel.target_id : rel.source_id;
                    const otherName = resolveEntityName(otherId);
                    return (
                      <li key={rel.id} className="flex items-start gap-2">
                        <span className="text-xs text-muted-foreground shrink-0 mt-0.5">
                          {isSource ? "→" : "←"}
                        </span>
                        <div className="min-w-0">
                          <span className="text-xs font-medium text-foreground block truncate">
                            {otherName}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {rel.type}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {properties.length === 0 && aliases.length === 0 && connected.length === 0 && (
              <div className="px-4 py-6 text-center">
                <p className="text-xs text-muted-foreground">No details available.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "facts" && (
          <div className="p-3 space-y-2">
            {factsLoading && (
              <p className="text-xs text-muted-foreground text-center py-4">Loading facts...</p>
            )}
            {!factsLoading && facts.length === 0 && (
              <div className="text-center py-6">
                <p className="text-xs text-muted-foreground">No facts found for this entity.</p>
              </div>
            )}
            {facts.map((fact) => (
              <FactCard key={fact.id} fact={fact} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
