import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { RefreshCw, BookOpen, AlertTriangle, Sparkles, Network, FileText } from "lucide-react";
import { useWiki } from "@/hooks/useWiki";
import { useWikiPage } from "@/hooks/useWikiPage";
import { useWikiRefresh } from "@/hooks/useWikiRefresh";
import { WikiLayout } from "@/components/wiki/WikiLayout";
import { OverviewPage } from "@/components/wiki/OverviewPage";
import { TopicPage } from "@/components/wiki/TopicPage";
import { GenericPage } from "@/components/wiki/GenericPage";
import { Button } from "@/components/ui/button";
import type { WikiPage, WikiPageNode } from "@/lib/types";

function WikiLoadingSkeleton() {
  return (
    <div className="flex h-full">
      <div className="w-[220px] shrink-0 border-r border-slate-200 bg-white p-4 space-y-2">
        <div className="h-4 bg-slate-100 rounded animate-pulse w-3/4" />
        <div className="h-3 bg-slate-100 rounded animate-pulse w-1/2 mt-3" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-7 bg-slate-100 rounded animate-pulse" />
        ))}
      </div>
      <div className="flex-1 p-8 space-y-4">
        <div className="h-3 bg-slate-100 rounded animate-pulse w-1/4" />
        <div className="h-7 bg-slate-100 rounded animate-pulse w-1/2" />
        <div className="h-3 bg-slate-100 rounded animate-pulse w-1/6" />
        <div className="space-y-2 mt-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-4 bg-slate-100 rounded animate-pulse" style={{ width: `${70 + (i % 3) * 10}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

interface WikiEmptyStateProps {
  onRefresh: () => void;
  isRefreshing: boolean;
  hasError: boolean;
}

function WikiEmptyState({ onRefresh, isRefreshing, hasError }: WikiEmptyStateProps) {
  return (
    <div className="min-h-full bg-muted/10 px-6 py-8">
      <div className="mx-auto w-full max-w-2xl rounded-2xl border border-border/70 bg-card/80 shadow-sm backdrop-blur-sm">
        <div className="px-6 py-8 text-center sm:px-10 sm:py-10">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
            {hasError ? (
              <AlertTriangle className="h-7 w-7 text-amber-500" />
            ) : (
              <BookOpen className="h-7 w-7 text-primary" />
            )}
          </div>

          <h3 className="text-xl font-semibold tracking-tight text-foreground">
            {hasError ? "Could not load wiki" : "Wiki not generated yet"}
          </h3>
          <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
            {hasError
              ? "The wiki is unavailable right now. Retry generation to rebuild this channel knowledge view."
              : "Generate a structured wiki to turn this channel history into topics, references, and easy-to-scan summaries."}
          </p>

          {!hasError && (
            <div className="mx-auto mt-6 grid max-w-xl gap-2.5 text-left sm:grid-cols-3">
              <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
                <Sparkles className="mb-2 h-4 w-4 text-primary" />
                <p className="text-xs font-medium text-foreground">Auto summaries</p>
                <p className="mt-1 text-xs text-muted-foreground">High-signal channel recap</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
                <Network className="mb-2 h-4 w-4 text-primary" />
                <p className="text-xs font-medium text-foreground">Topic map</p>
                <p className="mt-1 text-xs text-muted-foreground">Related pages and relationships</p>
              </div>
              <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
                <FileText className="mb-2 h-4 w-4 text-primary" />
                <p className="text-xs font-medium text-foreground">Reference pages</p>
                <p className="mt-1 text-xs text-muted-foreground">Context with source-backed detail</p>
              </div>
            </div>
          )}

          <div className="mt-7 flex justify-center">
            <Button
              onClick={onRefresh}
              disabled={isRefreshing}
              size="lg"
              className="px-5"
            >
              <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
              {isRefreshing
                ? hasError
                  ? "Retrying..."
                  : "Generating..."
                : hasError
                  ? "Retry Wiki Generation"
                  : "Generate Wiki"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function renderPage(
  page: WikiPage,
  topicPages: WikiPageNode[],
  onNavigate: (pageId: string) => void,
) {
  if (page.id === "overview" || (page.page_type === "fixed" && page.slug === "overview")) {
    return <OverviewPage page={page} topicPages={topicPages} onNavigate={onNavigate} />;
  }
  if (page.page_type === "topic" || page.page_type === "sub-topic") {
    return <TopicPage page={page} onNavigate={onNavigate} />;
  }
  return <GenericPage page={page} onNavigate={onNavigate} />;
}

export function WikiTab() {
  const { id: channelId } = useParams<{ id: string }>();
  const [activePageId, setActivePageId] = useState<string>("overview");

  const { data: wiki, isLoading, error, refetch } = useWiki(channelId);

  // Only fetch non-overview pages lazily
  const lazyPageId = activePageId !== "overview" ? activePageId : undefined;
  const { data: pageData, isLoading: isPageLoading } = useWikiPage(channelId, lazyPageId);

  const { mutate: triggerRefresh, isPending: isRefreshing } = useWikiRefresh(channelId);

  const handleRefresh = useCallback(async () => {
    await triggerRefresh();
    refetch();
  }, [triggerRefresh, refetch]);

  const handleNavigate = useCallback((pageId: string) => {
    setActivePageId(pageId);
  }, []);

  if (isLoading) {
    return <WikiLoadingSkeleton />;
  }

  if (error || !wiki) {
    return (
      <WikiEmptyState
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
        hasError={!!error}
      />
    );
  }

  // Resolve the active page
  const activePage: WikiPage | null =
    activePageId === "overview" ? wiki.overview : (pageData ?? null);

  const topicPages = wiki.structure.pages.filter((p) => p.page_type === "topic");

  // Show a loading indicator inside the layout when fetching a non-overview page
  const pageContent =
    isPageLoading || !activePage ? (
      <div className="flex items-center justify-center py-16">
        <RefreshCw className="w-5 h-5 animate-spin text-slate-400" />
      </div>
    ) : (
      renderPage(activePage, topicPages, handleNavigate)
    );

  return (
    <WikiLayout
      channelId={channelId!}
      structure={wiki.structure}
      activePage={activePage ?? wiki.overview}
      onNavigate={handleNavigate}
      onRefresh={handleRefresh}
      isRefreshing={isRefreshing}
    >
      {pageContent}
    </WikiLayout>
  );
}
