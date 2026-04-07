import { useEffect, useState, useCallback } from "react";
import { Maximize2, X, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });

interface MermaidBlockProps {
  chart: string;
}

function sanitizeMermaid(raw: string): string {
  let chart = raw.trim();
  chart = chart.replace(/(\w+)\s+--\s+([^-\n][^>\n]*?)\s+-->\s+(\w+)/g, "$1 -->|$2| $3");
  chart = chart.replace(/(\w+)\s+--\s+([^-\n][^-\n]*?)\s+---\s+(\w+)/g, "$1 ---|$2| $3");
  chart = chart.replace(/\[([^\]]*)\(([^)]*)\)([^\]]*)\]/g, (_, pre, inner, post) => `[${pre}${inner}${post}]`);
  return chart;
}

function simplifyMermaid(chart: string): string {
  const lines = chart.split("\n");
  const simplified: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("graph ") || trimmed.startsWith("flowchart ")) { simplified.push(trimmed); continue; }
    if (trimmed.startsWith("subgraph") || trimmed === "end" || trimmed.startsWith("style ") || trimmed.startsWith("classDef ")) continue;
    if (trimmed.match(/^\w+\s*-->/) || trimmed.match(/^\w+\s*---/)) {
      simplified.push(`    ${trimmed.replace(/-->?\|[^|]*\|/g, "-->").replace(/---?\|[^|]*\|/g, "---")}`);
    }
  }
  return simplified.join("\n") || "graph TD\n    A[No diagram available]";
}

export function MermaidBlock({ chart }: MermaidBlockProps) {
  const [error, setError] = useState<string | null>(null);
  const [svg, setSvg] = useState<string>("");
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const render = async () => {
      const sanitized = sanitizeMermaid(chart);
      try {
        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const result = await mermaid.render(id, sanitized);
        setSvg(result.svg);
        setError(null);
      } catch {
        try {
          const id2 = `mermaid-${Math.random().toString(36).slice(2)}`;
          const result2 = await mermaid.render(id2, simplifyMermaid(sanitized));
          setSvg(result2.svg);
          setError(null);
        } catch (err2) {
          setError(String(err2));
        }
      }
    };
    render();
  }, [chart]);

  const handleZoomIn = useCallback(() => setZoom(z => Math.min(z + 0.25, 3)), []);
  const handleZoomOut = useCallback(() => setZoom(z => Math.max(z - 0.25, 0.5)), []);
  const handleReset = useCallback(() => setZoom(1), []);

  if (error) {
    return (
      <details className="my-4 rounded-lg border border-muted bg-muted/30 p-3">
        <summary className="text-xs text-muted-foreground cursor-pointer">Diagram could not be rendered — click to view source</summary>
        <pre className="mt-2 text-xs text-muted-foreground overflow-auto whitespace-pre-wrap">{chart}</pre>
      </details>
    );
  }

  // For inline view: let SVG render at natural size, scroll if wider than container
  // Extract original width to decide scaling strategy
  const widthMatch = svg.match(/width="([\d.]+)"/);
  const origWidth = widthMatch ? parseFloat(widthMatch[1]) : 0;

  // If diagram is very wide (>800px), scale it down but keep readable
  const inlineSvg = origWidth > 800
    ? svg.replace(/<svg /, '<svg style="height:auto;min-height:250px" ')
    : svg.replace(/<svg /, '<svg style="width:100%;height:auto;min-height:200px" ');

  // For expanded view: force SVG to fill available width
  const expandedSvg = svg
    .replace(/width="[\d.]+"/, 'width="100%"')
    .replace(/height="[\d.]+"/, 'height="100%"')
    .replace(/<svg /, '<svg style="width:100%;height:auto;min-width:80vw" ');

  if (expanded) {
    return (
      <div className="fixed inset-0 z-[100] bg-background/95 backdrop-blur-md" onClick={() => setExpanded(false)}>
        {/* Toolbar */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 rounded-lg bg-card border border-border p-1 shadow-lg" onClick={e => e.stopPropagation()}>
          <button onClick={handleZoomOut} className="p-2 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Zoom out">
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="text-xs text-muted-foreground px-2 min-w-[3rem] text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={handleZoomIn} className="p-2 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Zoom in">
            <ZoomIn className="h-4 w-4" />
          </button>
          <button onClick={handleReset} className="p-2 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Reset zoom">
            <RotateCcw className="h-4 w-4" />
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button onClick={() => setExpanded(false)} className="p-2 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors" title="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Diagram — centered, scrollable when zoomed */}
        <div className="absolute inset-0 overflow-auto flex items-center justify-center pt-14 pb-8 px-8" onClick={e => e.stopPropagation()}>
          <div
            className="transition-transform duration-200"
            style={{ transform: `scale(${zoom})`, transformOrigin: "center center", minWidth: "70vw" }}
            dangerouslySetInnerHTML={{ __html: expandedSvg }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="group my-6">
      <div className="relative rounded-lg bg-muted/20 border border-border p-6 overflow-x-auto cursor-pointer min-h-[200px] flex items-center" onClick={() => setExpanded(true)}>
        {/* Expand hint */}
        <div className="absolute top-2 right-2 flex items-center gap-1.5 rounded-md bg-background/70 border border-border px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Maximize2 className="h-3 w-3 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground">Click to enlarge</span>
        </div>
        {/* SVG — responsive, scales to container */}
        <div className="w-full" dangerouslySetInnerHTML={{ __html: inlineSvg }} />
      </div>
    </div>
  );
}
