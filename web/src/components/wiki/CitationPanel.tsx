import type { WikiCitation } from "@/lib/types";
import { MediaBadge } from "./MediaBadge";

interface CitationPanelProps {
  citations: WikiCitation[];
}

export function CitationPanel({ citations }: CitationPanelProps) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-8 border-t border-border pt-6">
      <h3 className="text-sm font-semibold text-muted-foreground mb-3">Sources</h3>
      <div className="space-y-3">
        {citations.map((citation, i) => (
          <div
            key={citation.id}
            id={`citation-${i + 1}`}
            className="flex gap-3 text-sm rounded-md p-2 -mx-2 transition-all duration-300"
          >
            <span className="text-primary font-medium font-mono w-6 shrink-0">[{i + 1}]</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {citation.author && (
                  <span className="font-medium text-foreground">@{citation.author}</span>
                )}
                {citation.timestamp && (
                  <span className="text-muted-foreground/70 text-xs">{citation.timestamp}</span>
                )}
                {citation.media_type && (
                  <MediaBadge type={citation.media_type} name={citation.media_name} />
                )}
              </div>
              <p className="text-muted-foreground text-xs mt-0.5 line-clamp-2">{citation.text_excerpt}</p>
              {citation.permalink && citation.permalink.startsWith("http") && (
                <a
                  href={citation.permalink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary/80 hover:text-primary mt-0.5 inline-block"
                >
                  View original message ↗
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
