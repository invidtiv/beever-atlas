import { useState, useEffect, useRef } from "react";
import { Search, Brain, Tag, User, Sparkles } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

interface SearchResultItem {
  id: string;
  memory_text: string;
  quality_score: number;
  topic_tags: string[];
  entity_tags: string[];
  importance: string;
  author_name: string;
  message_ts: string;
  channel_id: string;
  similarity_score: number;
}

interface SearchResponse {
  results: SearchResultItem[];
  total: number;
  query: string;
}

function importanceBadgeClass(importance: string): string {
  if (importance === "high") return "bg-red-500/10 text-red-400";
  if (importance === "low") return "bg-muted text-muted-foreground";
  return "bg-amber-500/10 text-amber-400";
}

function SimilarityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/60 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] tabular-nums text-muted-foreground">{pct}%</span>
    </div>
  );
}

function ResultCard({ item }: { item: SearchResultItem }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="text-sm text-foreground leading-relaxed flex-1">{item.memory_text}</p>
        <span
          className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${importanceBadgeClass(item.importance)}`}
        >
          {item.importance}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3 mt-3">
        <SimilarityBar score={item.similarity_score} />

        {item.author_name && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <User size={11} />
            {item.author_name}
          </span>
        )}

        {item.channel_id && (
          <span className="text-xs text-muted-foreground">#{item.channel_id}</span>
        )}
      </div>

      {(item.topic_tags.length > 0 || item.entity_tags.length > 0) && (
        <div className="flex flex-wrap gap-1 mt-3">
          {item.topic_tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] bg-violet-500/10 text-violet-400 border border-violet-500/20"
            >
              <Tag size={9} />
              {tag}
            </span>
          ))}
          {item.entity_tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] bg-blue-500/10 text-blue-400 border border-blue-500/20"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-4">
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <div className="flex gap-3 mt-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-20" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce the query by 400ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // Fire search when debouncedQuery changes
  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (!trimmed) {
      setResults([]);
      setHasSearched(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setHasSearched(true);

    api
      .post<SearchResponse>("/api/search", { query: trimmed, limit: 20, threshold: 0.7 })
      .then((data) => {
        setResults(data.results);
      })
      .catch((err: Error) => {
        setError(err.message ?? "Search failed");
        setResults([]);
      })
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  return (
    <div className="min-h-full">
      <div className="max-w-[800px] mx-auto p-6 sm:p-8 lg:p-12">
        {/* Page header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="font-heading text-2xl tracking-tight text-foreground">
              Search
            </h1>
            <p className="text-sm text-muted-foreground">
              Semantic search across all extracted facts
            </p>
          </div>
        </div>

        {/* Search input */}
        <div className="relative mb-6">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search facts, entities, decisions…"
            className="w-full rounded-xl border border-border bg-card pl-9 pr-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-colors"
          />
        </div>

        {/* Results area */}
        {loading ? (
          <ResultsSkeleton />
        ) : error ? (
          <div className="rounded-xl border border-dashed border-red-500/30 bg-red-500/5 p-8 text-center">
            <p className="text-sm font-medium text-red-400">Search failed</p>
            <p className="text-xs text-muted-foreground mt-1">{error}</p>
          </div>
        ) : hasSearched && results.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-card p-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mx-auto mb-3">
              <Brain size={22} className="text-muted-foreground/40" />
            </div>
            <p className="text-sm font-medium text-foreground/70">No results found</p>
            <p className="text-xs text-muted-foreground mt-1">
              Try a different query or lower the similarity threshold.
            </p>
          </div>
        ) : !hasSearched ? (
          <div className="rounded-xl border border-dashed border-border bg-card p-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mx-auto mb-3">
              <Search size={22} className="text-muted-foreground/30" />
            </div>
            <p className="text-sm font-medium text-foreground/60">
              Search your team's knowledge
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Decisions, facts, and discussions from your connected channels. Connect and sync channels to start building searchable knowledge.
            </p>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground mb-3 tabular-nums">
              {results.length} result{results.length !== 1 ? "s" : ""}
            </p>
            <div className="space-y-3">
              {results.map((item) => (
                <ResultCard key={item.id} item={item} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
