import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { WikiPageNode } from "@/lib/types";

interface WikiSidebarProps {
  pages: WikiPageNode[];
  activePageId: string;
  onNavigate: (pageId: string) => void;
}

interface SidebarItemProps {
  node: WikiPageNode;
  isActive: boolean;
  onClick: () => void;
  indent?: boolean;
}

function SidebarItem({ node, isActive, onClick, indent = false }: SidebarItemProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 w-full rounded-md px-3 py-1.5 text-left text-sm transition-colors ${
        isActive
          ? "bg-primary/10 text-primary border-l-2 border-primary font-medium"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      } ${indent ? "pl-6" : ""}`}
    >
      <span className="text-xs text-muted-foreground/70 font-mono w-6 shrink-0">{node.section_number}</span>
      <span className="truncate">{node.title}</span>
      {node.memory_count > 0 && (
        <span className="ml-auto text-xs text-muted-foreground/70">{node.memory_count}</span>
      )}
    </button>
  );
}

export function WikiSidebar({ pages, activePageId, onNavigate }: WikiSidebarProps) {
  const [topicsExpanded, setTopicsExpanded] = useState(true);

  const topicPages = pages.filter((p) => p.page_type === "topic");
  const fixedPages = pages.filter((p) => p.page_type === "fixed");

  const overviewPage = fixedPages.find((p) => p.id === "overview");
  const afterTopicPages = fixedPages.filter((p) => p.id !== "overview");

  return (
    <nav className="px-2 pb-4">
      {overviewPage && (
        <SidebarItem
          node={overviewPage}
          isActive={activePageId === overviewPage.id}
          onClick={() => onNavigate(overviewPage.id)}
        />
      )}

      {topicPages.length > 0 && (
        <div className="mt-1">
          <button
            onClick={() => setTopicsExpanded(!topicsExpanded)}
            className="flex items-center gap-1 w-full px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground"
          >
            {topicsExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            Topics
            <span className="ml-auto text-muted-foreground/70 normal-case font-normal">
              ({topicPages.length})
            </span>
          </button>
          {topicsExpanded &&
            topicPages.map((page) => (
              <SidebarItem
                key={page.id}
                node={page}
                isActive={activePageId === page.id}
                onClick={() => onNavigate(page.id)}
                indent
              />
            ))}
        </div>
      )}

      {afterTopicPages.map((page) => (
        <SidebarItem
          key={page.id}
          node={page}
          isActive={activePageId === page.id}
          onClick={() => onNavigate(page.id)}
        />
      ))}
    </nav>
  );
}
