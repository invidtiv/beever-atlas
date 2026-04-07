import { type ReactNode, useState, useCallback, useRef } from "react";
import { Download } from "lucide-react";
import { WikiSidebar } from "./WikiSidebar";
import { WikiBreadcrumb } from "./WikiBreadcrumb";
import { FreshnessBadge } from "./FreshnessBadge";
import { WikiTableOfContents } from "./WikiTableOfContents";
import type { WikiStructure, WikiPage } from "@/lib/types";

interface WikiLayoutProps {
  channelId: string;
  structure: WikiStructure;
  activePage: WikiPage;
  onNavigate: (pageId: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  children: ReactNode;
}

const MIN_WIDTH = 180;
const MAX_WIDTH = 400;
const DEFAULT_WIDTH = 240;

export function WikiLayout({
  channelId,
  structure,
  activePage,
  onNavigate,
  onRefresh,
  isRefreshing,
  children,
}: WikiLayoutProps) {
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WIDTH);
  const isDragging = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = moveEvent.clientX - startX;
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + delta));
      setSidebarWidth(newWidth);
    };

    const onMouseUp = () => {
      isDragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [sidebarWidth]);

  return (
    <div className="flex h-full">
      {/* Left Sidebar */}
      <div
        className="shrink-0 border-r border-border bg-background overflow-y-auto"
        style={{ width: sidebarWidth }}
      >
        <div className="p-4 pb-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground truncate">Wiki</h3>
            <a
              href={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/channels/${channelId}/wiki/download`}
              download
              className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="Download as Markdown"
            >
              <Download className="h-3.5 w-3.5" />
            </a>
          </div>
          <FreshnessBadge
            isStale={structure.is_stale}
            generatedAt={structure.generated_at}
            onRefresh={onRefresh}
            isRefreshing={isRefreshing}
          />
        </div>
        <WikiSidebar
          pages={structure.pages}
          activePageId={activePage.id}
          onNavigate={onNavigate}
        />
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className="w-1 shrink-0 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 transition-colors"
      />

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto min-w-0">
        <div className="max-w-4xl mx-auto px-8 py-6" ref={contentRef}>
          <WikiBreadcrumb page={activePage} />
          {children}
        </div>
      </div>

      {/* Right TOC Sidebar */}
      <div className="hidden xl:block w-48 shrink-0 overflow-y-auto">
        <div className="sticky top-0 px-4 py-8">
          <WikiTableOfContents contentRef={contentRef} />
        </div>
      </div>
    </div>
  );
}
