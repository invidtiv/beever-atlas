/**
 * Wiki graph view — renders the channel's wiki pages, their hierarchy
 * (parent/child edges), `[[wikilink]]` cross-references, and a central
 * Channel hub via Cytoscape.js.
 *
 * Cytoscape is loaded ONLY at mount time via dynamic ``import()`` so
 * the wiki tab's main bundle never pays its weight (§6.13). Until the
 * dynamic import resolves, a lightweight skeleton shows in place of
 * the canvas.
 *
 * Click a wiki node → opens an inline preview panel on the right with
 * the page's title, summary, section number, and an "Open in Wiki tab"
 * button that routes to the wiki tab WITH the right page selected via
 * a ``?page={pageId}`` query param. No 404s, no out-of-context
 * navigation.
 */
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { X, ExternalLink, Loader2 } from "lucide-react";
import { useWikiGraph, type WikiGraphPayload, type WikiGraphNode } from "@/hooks/useWikiGraph";
import { useWikiPage } from "@/hooks/useWikiPage";
import { WikiMarkdown } from "@/components/wiki/WikiMarkdown";

type LayoutKey = "concentric" | "cose" | "dagre" | "grid";
type KindFilter = "all" | "topic" | "entity" | "decisions" | "faq" | "action_items";
type WindowFilter = "all" | "1h" | "24h" | "7d";

interface FilterState {
  kind: KindFilter;
  touchedWithin: WindowFilter;
  minCitations: number;
}

const WINDOW_MS: Record<WindowFilter, number> = {
  all: Number.POSITIVE_INFINITY,
  "1h": 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
};

function applyFilters(
  payload: WikiGraphPayload,
  filters: FilterState,
): WikiGraphPayload {
  const now = Date.now();
  const cutoff =
    filters.touchedWithin === "all"
      ? null
      : now - WINDOW_MS[filters.touchedWithin];

  const nodes = payload.nodes.filter((n) => {
    // Channel hub always survives; the graph would float without it.
    if (n.data.kind === "channel") return true;
    if (filters.kind === "all") return true;
    if (filters.kind === "entity") return n.data.kind === "entity";
    if (n.data.kind !== "wiki") return false;
    return n.data.page_kind === filters.kind;
  });

  // Citation density filter — count incoming edges per node.
  const incoming = new Map<string, number>();
  for (const edge of payload.edges) {
    incoming.set(edge.data.target, (incoming.get(edge.data.target) ?? 0) + 1);
  }

  const visibleNodes = nodes.filter((n) => {
    if (filters.minCitations <= 0) return true;
    if (n.data.kind !== "wiki") return true;
    if (cutoff !== null) {
      const ts = n.data.last_updated ? Date.parse(n.data.last_updated) : 0;
      if (!Number.isFinite(ts) || ts < cutoff) return false;
    }
    return (incoming.get(n.data.id) ?? 0) >= filters.minCitations;
  });

  const visibleIds = new Set(visibleNodes.map((n) => n.data.id));
  const visibleEdges = payload.edges.filter(
    (e) => visibleIds.has(e.data.source) && visibleIds.has(e.data.target),
  );

  return {
    channel_id: payload.channel_id,
    nodes: visibleNodes,
    edges: visibleEdges,
  };
}

interface WikiGraphProps {
  channelId?: string;
}

interface WikiGraphSelectionData {
  id: string;
  pageId?: string;
  slug?: string;
  label: string;
  kind?: string;
  pageKind?: string;
  sectionNumber?: string;
  summary?: string;
  memoryCount?: number;
  lastUpdated?: string;
  isChannel: boolean;
  isEntity: boolean;
}

function selectionFromNode(node: WikiGraphNode): WikiGraphSelectionData {
  const d = node.data ?? {};
  const dAny = d as Record<string, unknown>;
  return {
    id: String(d.id ?? ""),
    pageId:
      typeof dAny.page_id === "string"
        ? dAny.page_id
        : typeof dAny.id === "string"
          ? dAny.id
          : undefined,
    slug: typeof dAny.slug === "string" ? dAny.slug : undefined,
    label: typeof d.label === "string" ? d.label : String(d.id ?? ""),
    kind: typeof d.kind === "string" ? d.kind : undefined,
    pageKind: typeof d.page_kind === "string" ? d.page_kind : undefined,
    sectionNumber:
      typeof dAny.section_number === "string"
        ? (dAny.section_number as string)
        : undefined,
    summary: typeof dAny.summary === "string" ? (dAny.summary as string) : undefined,
    memoryCount:
      typeof dAny.memory_count === "number"
        ? (dAny.memory_count as number)
        : undefined,
    lastUpdated:
      typeof d.last_updated === "string" ? d.last_updated : undefined,
    isChannel: d.kind === "channel",
    isEntity: d.kind === "entity",
  };
}

// Per-kind colors keep the graph legible when node count is large.
const KIND_COLORS: Record<string, string> = {
  channel: "#a855f7", // purple — central hub
  wiki_overview: "#0ea5e9", // sky — overview pages (page_kind="fixed" + slug=overview)
  wiki_fixed: "#22c55e", // green — fixed pages (people, faq, etc.)
  wiki_topic: "#3b82f6", // blue — topic pages
  wiki_subtopic: "#60a5fa", // light blue — sub-topics
  wiki_entity_page: "#f59e0b", // amber — entity wiki pages
  wiki_decisions: "#ef4444", // red — decisions
  wiki_faq: "#8b5cf6", // violet — FAQ
  wiki_action_items: "#14b8a6", // teal — action items
  wiki_default: "#3b82f6",
  entity: "#10b981", // emerald — graph entity nodes
};

function colorForNode(node: WikiGraphNode): string {
  const d = node.data ?? {};
  if (d.kind === "channel") return KIND_COLORS.channel;
  if (d.kind === "entity") return KIND_COLORS.entity;
  const slug = (d as Record<string, unknown>).slug as string | undefined;
  const pk = d.page_kind || "topic";
  if (slug === "overview") return KIND_COLORS.wiki_overview;
  if (pk === "fixed") return KIND_COLORS.wiki_fixed;
  if (pk === "sub-topic") return KIND_COLORS.wiki_subtopic;
  if (pk === "entity") return KIND_COLORS.wiki_entity_page;
  if (pk === "decisions") return KIND_COLORS.wiki_decisions;
  if (pk === "faq") return KIND_COLORS.wiki_faq;
  if (pk === "action_items") return KIND_COLORS.wiki_action_items;
  if (pk === "topic") return KIND_COLORS.wiki_topic;
  return KIND_COLORS.wiki_default;
}

// Pre-build elements with per-node color so the cytoscape style sheet
// can reference data(color) directly — keeps the style block small.
// Labels are truncated to ~28 chars to stop the outer ring from
// overlapping into an unreadable crush — the full title is on the
// preview panel + tooltip on hover, so the truncation is purely
// visual relief.
function _truncateLabel(raw: string, max = 30): string {
  const s = (raw || "").trim();
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}

/**
 * Cleaner labels: drop the "§N" prefix the previous pass added — it
 * was visually noisy at this density. Section number lives on the
 * preview panel + tooltip; the label just carries the title.
 */
function buildLabel(node: WikiGraphNode): string {
  const d = node.data ?? {};
  const raw = (typeof d.label === "string" ? d.label : String(d.id ?? "")).trim();
  return _truncateLabel(raw);
}

/**
 * Inline SVG document icon, base64-encoded as a data URL so cytoscape
 * can use it as ``background-image`` without a network round-trip.
 * Shape: rounded paper page with a folded top-right corner — the
 * universal "document" affordance. White stroke on transparent fill so
 * it picks up the per-kind ``data(color)`` background underneath.
 */
const DOC_ICON_SVG = encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M14 3 H6 a2 2 0 0 0 -2 2 v14 a2 2 0 0 0 2 2 h12 a2 2 0 0 0 2 -2 V9 z"/>' +
    '<polyline points="14 3 14 9 20 9"/>' +
    '<line x1="8" y1="13" x2="16" y2="13"/>' +
    '<line x1="8" y1="17" x2="13" y2="17"/>' +
    "</svg>",
);
const DOC_ICON_URL = `data:image/svg+xml;utf8,${DOC_ICON_SVG}`;

const HOME_ICON_SVG = encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="#ffffff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M3 9 L12 2 L21 9 V20 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 z"/>' +
    '<polyline points="9 22 9 12 15 12 15 22"/>' +
    "</svg>",
);
const HOME_ICON_URL = `data:image/svg+xml;utf8,${HOME_ICON_SVG}`;

function buildElements(filtered: WikiGraphPayload): unknown[] {
  const out: unknown[] = [];
  for (const node of filtered.nodes) {
    const isChannel = node.data.kind === "channel";
    const isEntity = node.data.kind === "entity";
    const isWiki = node.data.kind === "wiki";
    out.push({
      data: {
        ...node.data,
        displayLabel: buildLabel(node),
        color: colorForNode(node),
        // Visual identity per kind:
        //   • channel hub = chunky home-icon disc (root of the wiki)
        //   • wiki page   = small rounded square with document icon
        //   • entity      = tiny dot (Obsidian-style, hints at the
        //                   adjacent entity-graph surface)
        nodeShape: isEntity ? "ellipse" : "round-rectangle",
        nodeWidth: isChannel ? 60 : isWiki ? 38 : 16,
        nodeHeight: isChannel ? 60 : isWiki ? 38 : 16,
        // Per-kind icon glyph rendered as a centered background-image.
        // The base color of the disc is ``data(color)`` so kinds remain
        // distinguishable; the white-stroke icon sits on top.
        icon: isChannel ? HOME_ICON_URL : isWiki ? DOC_ICON_URL : "",
        labelSize: isChannel ? 13 : isWiki ? 11 : 10,
        labelWeight: isChannel ? 700 : 500,
      },
    });
  }
  for (const edge of filtered.edges) {
    out.push({ data: { ...edge.data } });
  }
  return out;
}

export function WikiGraph({ channelId: channelIdOverride }: WikiGraphProps = {}) {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const channelId = channelIdOverride ?? params.id;
  const { data, isLoading, error, refetch } = useWikiGraph(channelId);
  const [filters, setFilters] = useState<FilterState>({
    kind: "all",
    touchedWithin: "all",
    minCitations: 0,
  });
  // Default to concentric — radial mind-map with the channel hub at
  // the center and pages clustered by kind in expanding rings. This
  // matches the actual data shape (mostly star-graph: 1 channel + N
  // leaf pages) far better than dagre's tree, and visually telegraphs
  // "wiki = a constellation of documents around a channel." Entity
  // graph uses force-directed fcose; the difference is immediate.
  const [layout, setLayout] = useState<LayoutKey>("concentric");
  const containerRef = useRef<HTMLDivElement | null>(null);
  // ``unknown`` because cytoscape's type surface (Core, ElementDefinition)
  // adds a non-trivial type-import; the runtime methods we touch
  // (``on`` + ``destroy``) are narrowed at use site.
  const cyRef = useRef<unknown>(null);
  const [cytoscapeReady, setCytoscapeReady] = useState(false);
  const [cytoscapeError, setCytoscapeError] = useState<string | null>(null);
  const [selection, setSelection] = useState<WikiGraphSelectionData | null>(null);

  const filtered = useMemo(
    () => (data ? applyFilters(data, filters) : null),
    [data, filters],
  );

  // Selection handler held in a ref so the cytoscape mount effect does
  // NOT depend on its identity — channelId / navigate identity changes
  // would otherwise destroy + remount the entire graph (visible flicker).
  const handleNodeTapRef = useRef<(nodeData: Record<string, unknown>) => void>(
    () => undefined,
  );
  handleNodeTapRef.current = useCallback((nodeData: Record<string, unknown>) => {
    // Empty data → background tap; clear selection.
    if (!nodeData || !nodeData.id) {
      setSelection(null);
      return;
    }
    const fakeNode: WikiGraphNode = { data: nodeData as WikiGraphNode["data"] };
    const sel = selectionFromNode(fakeNode);
    if (sel.isEntity) {
      // Entity nodes navigate to the entity-graph view inside the
      // Agent Memory tab — the standalone /graph route was removed
      // when the IA collapsed graphs into their parent tabs. The
      // ?view=graph param keeps the entity-graph surface; ?entity is
      // forwarded for downstream deep-link handlers.
      if (channelId) {
        const entityName = sel.id.startsWith("entity:")
          ? sel.id.slice(7)
          : sel.label;
        navigate(`/channels/${channelId}/memories?view=graph&entity=${encodeURIComponent(entityName)}`);
      }
      return;
    }
    // Wiki nodes + channel hub → open inline preview panel.
    setSelection(sel);
  }, [channelId, navigate]);

  // Double-tap shortcut — same selection-derivation logic but routes
  // straight to the wiki tab with the page selected, skipping the
  // panel preview. Operators who already know which page they want
  // don't have to single-click → "Open in Wiki tab".
  const handleNodeDoubleTapRef = useRef<(nodeData: Record<string, unknown>) => void>(
    () => undefined,
  );
  handleNodeDoubleTapRef.current = useCallback(
    (nodeData: Record<string, unknown>) => {
      if (!nodeData || !nodeData.id || !channelId) return;
      const fakeNode: WikiGraphNode = { data: nodeData as WikiGraphNode["data"] };
      const sel = selectionFromNode(fakeNode);
      if (sel.isEntity || sel.isChannel || !sel.pageId) return;
      navigate(
        `/channels/${channelId}/wiki?page=${encodeURIComponent(sel.pageId)}`,
      );
    },
    [channelId, navigate],
  );

  const elements = useMemo(
    () => (filtered ? buildElements(filtered) : []),
    [filtered],
  );

  useEffect(() => {
    let alive = true;
    type CyTapEvent = {
      target: {
        id?: () => string;
        data?: () => Record<string, unknown>;
      };
    };
    type CyInstance = {
      // Cytoscape's ``on`` is overloaded: 2-arg form (event, handler) for
      // canvas-wide events, 3-arg form (event, selector, handler) for
      // element-bound events. Both are valid runtime calls.
      on: {
        (event: string, handler: (e: CyTapEvent) => void): void;
        (event: string, selector: string, handler: (e: CyTapEvent) => void): void;
      };
      fit: (eles?: unknown, padding?: number) => void;
      zoom: (level?: number) => number;
      minZoom: (level: number) => void;
      maxZoom: (level: number) => void;
      container: () => HTMLElement;
      destroy: () => void;
    };
    let cy: CyInstance | null = null;
    if (!filtered || !containerRef.current) return;

    (async () => {
      try {
        const module = await import("cytoscape");
        if (!alive) return;
        const cytoscape = (module as { default: unknown }).default ?? module;
        // Register cytoscape-dagre once for hierarchical tree layout —
        // wikis ARE structured document trees, dagre is the right tool.
        // The package ships untyped; runtime registration is fine.
        try {
          // @ts-expect-error — cytoscape-dagre has no .d.ts
          const dagre = (await import("cytoscape-dagre")).default;
          (cytoscape as { use: (ext: unknown) => void }).use(dagre);
        } catch {
          /* already registered or import failed — dagre dropdown will silently fall back */
        }
        const factory = cytoscape as (config: Record<string, unknown>) => CyInstance;
        cy = factory({
          container: containerRef.current,
          elements,
          wheelSensitivity: 0.2,
          style: [
            {
              // Wiki + channel nodes: rounded square card with a
              // centered SVG icon + the title below. The icon is the
              // single strongest visual signal that this is a *wiki
              // graph of documents* — distinct from entity-graph dots.
              selector: "node",
              style: {
                shape: "data(nodeShape)" as unknown as "round-rectangle",
                label: "data(displayLabel)",
                "text-valign": "bottom",
                "text-halign": "center",
                "text-margin-y": 8,
                color: "#e2e8f0",
                "font-size": "data(labelSize)",
                "font-weight": "data(labelWeight)",
                "text-wrap": "wrap",
                "text-max-width": "120px",
                "text-outline-color": "#0f172a",
                "text-outline-width": 1,
                "background-color": "data(color)",
                "background-image": "data(icon)",
                "background-fit": "contain",
                "background-image-opacity": 0.95,
                "background-width": "60%",
                "background-height": "60%",
                width: "data(nodeWidth)" as unknown as number,
                height: "data(nodeHeight)" as unknown as number,
                "border-width": 1,
                "border-color": "rgba(255,255,255,0.12)",
                "transition-property":
                  "background-color, border-color, width, height, opacity",
                "transition-duration": 150,
              } as unknown as cytoscape.Css.Node,
            },
            {
              // Wiki page cards keep the document-icon presentation +
              // a subtle paper-edge border so they read as documents
              // rather than colored tiles.
              selector: "node[kind = 'wiki']",
              style: {
                "border-width": 1.5,
                "border-color": "rgba(255,255,255,0.18)",
                "background-opacity": 0.92,
              },
            },
            {
              // Channel hub: bigger disc with the "home" icon. Reads
              // as the root node of the wiki space.
              selector: "node[kind = 'channel']",
              style: {
                shape: "round-rectangle" as unknown as "round-rectangle",
                "border-width": 2.5,
                "border-color": "rgba(168,85,247,0.7)",
                "background-opacity": 0.95,
                color: "#faf5ff",
                "font-weight": 700,
              },
            },
            {
              // Entity nodes (rare in wiki graph) keep the dot+caption
              // form — hints at the entity-graph surface they belong to.
              selector: "node[kind = 'entity']",
              style: {
                "background-image": "none",
                "border-width": 1,
                "border-color": "rgba(255,255,255,0.18)",
                "background-opacity": 1,
              },
            },
            {
              selector: "node.dimmed",
              style: { opacity: 0.25 },
            },
            {
              selector: "node.highlighted",
              style: {
                "border-width": 3,
                "border-color": "#fbbf24",
                "z-index": 999,
              },
            },
            {
              selector: "node.neighbor",
              style: {
                "border-width": 2,
                "border-color": "#facc15",
              },
            },
            {
              selector: "node:selected",
              style: {
                "border-color": "#fbbf24",
                "border-width": 3,
              },
            },
            {
              // Hover affordance — node bumps + edge highlights so the
              // operator can see the click target clearly before
              // committing.
              selector: "node:active",
              style: {
                "border-width": 3,
                "border-color": "#facc15",
                "overlay-opacity": 0,
              },
            },
            {
              selector: "edge",
              style: {
                width: 1.5,
                "line-color": "rgba(148,163,184,0.5)",
                "target-arrow-color": "rgba(148,163,184,0.6)",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                "arrow-scale": 0.8,
                "transition-property": "line-color, opacity, width",
                "transition-duration": 150,
              },
            },
            { selector: "edge.dimmed", style: { opacity: 0.1 } },
            {
              selector: "edge.highlighted",
              style: {
                width: 2.5,
                "line-color": "#facc15",
                "target-arrow-color": "#facc15",
                "z-index": 999,
              },
            },
            {
              // Hierarchy edges (channel-hub → page) — purple SOLID,
              // medium width, prominent arrow. Reads as "belongs to
              // this channel".
              selector: "edge[kind = 'belongs_to']",
              style: {
                "line-color": "rgba(168,85,247,0.5)",
                "target-arrow-color": "rgba(168,85,247,0.7)",
                "line-style": "solid",
                width: 1.5,
              },
            },
            {
              // Hierarchy edges (parent page → child page) — sky-blue
              // SOLID, slightly thicker. Tree-trunk feel.
              selector: "edge[kind = 'child_of']",
              style: {
                "line-color": "rgba(96,165,250,0.7)",
                "target-arrow-color": "rgba(96,165,250,0.8)",
                "line-style": "solid",
                width: 2,
              },
            },
            {
              // Cross-references (wiki → wiki [[wikilink]]) — DASHED
              // amber, light width. Reads as "see also", visually
              // distinct from the hierarchy spine.
              selector: "edge[kind = 'references_wiki']",
              style: {
                "line-color": "rgba(251,191,36,0.6)",
                "target-arrow-color": "rgba(251,191,36,0.7)",
                "line-style": "dashed",
                width: 1.2,
              },
            },
            {
              // Cross-references to entities — DOTTED emerald, even
              // lighter, hint of "extends to the knowledge graph".
              selector: "edge[kind = 'references_entity']",
              style: {
                "line-style": "dotted",
                "line-color": "rgba(16,185,129,0.55)",
                "target-arrow-color": "rgba(16,185,129,0.65)",
                width: 1,
              },
            },
          ],
          layout:
            layout === "concentric"
              ? {
                  // Channel hub at the center, page cards in concentric
                  // rings ordered by importance: fixed-purpose pages
                  // (Overview, FAQ, Decisions) close in, free-form
                  // topics next, sub-topics on the outer ring,
                  // entities on the periphery. Each ring stratifies
                  // the wiki visually so the operator sees the
                  // structure at a glance.
                  name: "concentric",
                  fit: true,
                  padding: 70,
                  minNodeSpacing: 60,
                  spacingFactor: 1.5,
                  startAngle: (3 / 2) * Math.PI,
                  sweep: 2 * Math.PI,
                  clockwise: true,
                  concentric: (node: { data: (k: string) => unknown }) => {
                    const kind = node.data("kind");
                    if (kind === "channel") return 1000;
                    if (kind === "entity") return 5;
                    const pageKind = (node.data("page_kind") as string) || "";
                    const slug = (node.data("slug") as string) || "";
                    if (slug === "overview") return 500;
                    if (pageKind === "fixed") return 300;
                    if (pageKind === "sub-topic") return 30;
                    return 100;
                  },
                  levelWidth: () => 1,
                  animate: true,
                  animationDuration: 700,
                  animationEasing: "ease-out-cubic",
                }
              : layout === "dagre"
                ? {
                    // Top-down hierarchy with breathing room for the
                    // new pill-shaped wiki cards (label-driven width
                    // = ~120-200 px). Bumped nodeSep + rankSep so
                    // sibling cards don't crowd, and tree levels
                    // visibly stratify.
                    name: "dagre",
                    rankDir: "TB",
                    animate: true,
                    animationDuration: 600,
                    animationEasing: "ease-out-cubic",
                    nodeSep: 110,
                    edgeSep: 40,
                    rankSep: 140,
                    fit: true,
                    padding: 50,
                  }
                : layout === "grid"
                  ? { name: "grid", animate: false, padding: 40 }
                  : {
                      // Cose tuned for ~70 nodes on a typical channel.
                      // Earlier attempt at very high nodeRepulsion
                      // pushed nodes so far apart that ``fit:true``
                      // crushed them into tiny dots. These values give
                      // Obsidian-style spacing without that scale-down.
                      name: "cose",
                      animate: false,
                      idealEdgeLength: 90,
                      nodeOverlap: 12,
                      nodeRepulsion: 400_000,
                      edgeElasticity: 80,
                      gravity: 0.4,
                      numIter: 1500,
                      padding: 50,
                      fit: true,
                    },
        });
        // Click — Obsidian-style: highlight the clicked node + its
        // direct neighbors, dim the rest, fire selection callback.
        const cyAny = cy as unknown as {
          elements: () => {
            removeClass: (c: string) => void;
            addClass: (c: string) => void;
          };
          getElementById: (id: string) => {
            length: number;
            data: () => Record<string, unknown>;
            closedNeighborhood: () => {
              removeClass: (c: string) => void;
              addClass: (c: string) => void;
              edges: () => { addClass: (c: string) => void };
            };
          };
          fit: (eles?: unknown, padding?: number) => void;
          zoom: (level?: number) => number;
          minZoom: (level: number) => void;
          maxZoom: (level: number) => void;
          container: () => HTMLElement;
        };
        // Cap zoom-out so cose's dispersion never crushes labels into
        // dots. Cap zoom-in for trackpad-pinch sanity.
        cyAny.minZoom(0.3);
        cyAny.maxZoom(2.5);
        cyAny.fit(undefined, 60);
        // If cose pushed the zoom below 0.6, scale back up so labels
        // are readable. Trades graph-area-coverage for legibility.
        const z = cyAny.zoom();
        if (z < 0.6) cyAny.zoom(0.6);
        // Pointer cursor over nodes signals interactivity.
        try {
          cyAny.container().style.cursor = "default";
        } catch {
          /* no-op when container() returns nothing in a teardown race */
        }
        const clearHighlights = () => {
          cyAny.elements().removeClass("dimmed highlighted neighbor");
        };
        cy.on("tap", "node", (e) => {
          const evtTarget = (e as unknown as {
            target: {
              id: () => string;
              data: () => Record<string, unknown>;
              closedNeighborhood: () => {
                removeClass: (c: string) => void;
                addClass: (c: string) => void;
                edges: () => { addClass: (c: string) => void };
              };
            };
          }).target;
          const nodeData = evtTarget.data();
          // Fire selection FIRST so the panel always opens — the
          // highlight pass below is purely cosmetic and must never
          // block the user-visible feedback if cytoscape throws.
          handleNodeTapRef.current(nodeData);
          try {
            const nodeId = evtTarget.id();
            cyAny.elements().removeClass("dimmed highlighted neighbor");
            cyAny.elements().addClass("dimmed");
            const neighborhood = evtTarget.closedNeighborhood();
            neighborhood.removeClass("dimmed");
            neighborhood.addClass("neighbor");
            neighborhood.edges().addClass("highlighted");
            const ele = cyAny.getElementById(nodeId);
            if (ele.length > 0) {
              ele.closedNeighborhood().removeClass("dimmed");
            }
          } catch {
            /* highlight is best-effort — never block selection on it */
          }
        });
        // Background tap clears the selection + highlights.
        cy.on("tap", (e) => {
          const evtTarget = (e as unknown as { target: unknown }).target;
          if (evtTarget === cy) {
            clearHighlights();
            handleNodeTapRef.current({});
          }
        });
        // Double-tap on a node — skip the panel and navigate straight
        // to the wiki tab with that page selected. Operators who know
        // what they want shouldn't need a two-click flow.
        cy.on("dbltap", "node", (e) => {
          const data = (
            e as unknown as { target: { data: () => Record<string, unknown> } }
          ).target.data();
          handleNodeDoubleTapRef.current(data);
        });
        // Hover affordance — pointer cursor flips on, the node grows
        // 1.15x so the click target is visually obvious. Restored on
        // mouseout.
        cy.on("mouseover", "node", () => {
          try {
            cyAny.container().style.cursor = "pointer";
          } catch {
            /* no-op */
          }
        });
        cy.on("mouseout", "node", () => {
          try {
            cyAny.container().style.cursor = "default";
          } catch {
            /* no-op */
          }
        });
        cyRef.current = cy;
        setCytoscapeReady(true);
      } catch (err) {
        if (!alive) return;
        const message = err instanceof Error ? err.message : "cytoscape failed to load";
        setCytoscapeError(message);
      }
    })();

    return () => {
      alive = false;
      try {
        if (cy) cy.destroy();
      } catch {
        /* destroy is best-effort */
      }
      cyRef.current = null;
    };
    // ``handleNodeTapRef`` intentionally absent — the ref's `.current`
    // is updated above so cytoscape always sees the latest closure
    // without needing to remount.
  }, [elements, layout]);

  // When the side panel opens or closes, the canvas flex-1 column
  // changes width. Cytoscape's internal canvas does NOT auto-resize on
  // container reflow — without this, the graph gets clipped or the
  // panel sits behind a stale-sized canvas. Schedule on next frame so
  // the DOM has settled before we measure.
  useEffect(() => {
    const handle = window.requestAnimationFrame(() => {
      const cy = cyRef.current as
        | { resize: () => void; fit: (eles?: unknown, padding?: number) => void }
        | null;
      if (!cy) return;
      try {
        cy.resize();
        cy.fit(undefined, 60);
      } catch {
        /* no-op — cytoscape may have torn down between schedule + fire */
      }
    });
    return () => window.cancelAnimationFrame(handle);
  }, [selection !== null]);

  return (
    <div className="flex h-full flex-col" data-testid="wiki-graph-root">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-card/60 px-5 py-3">
        <h2 className="text-base font-semibold text-foreground whitespace-nowrap">
          Wiki graph
        </h2>
        <select
          aria-label="Filter by page kind"
          value={filters.kind}
          onChange={(e) =>
            setFilters((s) => ({ ...s, kind: e.target.value as KindFilter }))
          }
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          data-testid="wiki-graph-filter-kind"
        >
          <option value="all">All kinds</option>
          <option value="topic">Topic</option>
          <option value="entity">Entity</option>
          <option value="decisions">Decisions</option>
          <option value="faq">FAQ</option>
          <option value="action_items">Action items</option>
        </select>
        <select
          aria-label="Filter by last touched"
          value={filters.touchedWithin}
          onChange={(e) =>
            setFilters((s) => ({
              ...s,
              touchedWithin: e.target.value as WindowFilter,
            }))
          }
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
        >
          <option value="all">Any time</option>
          <option value="1h">Last hour</option>
          <option value="24h">Last 24h</option>
          <option value="7d">Last 7d</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-muted-foreground whitespace-nowrap">
          Citation density ≥
          <input
            aria-label="Minimum citation density"
            type="number"
            min={0}
            max={20}
            value={filters.minCitations}
            onChange={(e) =>
              setFilters((s) => ({
                ...s,
                minCitations: Number.isNaN(parseInt(e.target.value, 10))
                  ? 0
                  : parseInt(e.target.value, 10),
              }))
            }
            className="w-16 rounded-md border border-border bg-background px-2 py-1 text-xs"
          />
        </label>
        <select
          aria-label="Graph layout"
          value={layout}
          onChange={(e) => setLayout(e.target.value as LayoutKey)}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
        >
          <option value="concentric">Concentric (hub-first)</option>
          <option value="dagre">Dagre (top-down)</option>
          <option value="cose">Cose (force-directed)</option>
          <option value="grid">Grid</option>
        </select>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs hover:bg-muted whitespace-nowrap"
        >
          Refresh
        </button>
        <Legend />
      </header>

      <div className="relative flex flex-1 min-h-0 overflow-hidden">
        {/* ``min-w-0`` so the flex item can shrink past the cytoscape
            internal canvas's intrinsic width when the panel opens.
            Without it, the canvas pins the flex parent at its content
            size and pushes the panel off-screen to the right. */}
        <div className="relative flex-1 min-w-0 overflow-hidden bg-muted/10">
          {error && (
            <div
              className="absolute inset-0 flex items-center justify-center text-sm text-red-500"
              role="alert"
            >
              {error}
            </div>
          )}
          {cytoscapeError && (
            <div
              className="absolute inset-0 flex items-center justify-center text-sm text-amber-500"
              role="alert"
            >
              Graph engine failed to load: {cytoscapeError}
            </div>
          )}
          {(isLoading || (!cytoscapeReady && !cytoscapeError)) && (
            <div
              className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground"
              data-testid="wiki-graph-loading"
            >
              Loading wiki graph…
            </div>
          )}
          <div
            ref={containerRef}
            className="h-full w-full"
            data-testid="wiki-graph-canvas"
            data-node-count={filtered?.nodes.length ?? 0}
            data-edge-count={filtered?.edges.length ?? 0}
          />
        </div>

        {selection && (
          <WikiGraphPanel
            channelId={channelId}
            selection={selection}
            onClose={() => setSelection(null)}
          />
        )}
      </div>

      <footer className="flex items-center justify-between border-t border-border bg-card/60 px-5 py-2 text-xs text-muted-foreground">
        <span>
          {filtered?.nodes.length ?? 0} nodes · {filtered?.edges.length ?? 0} edges
          {selection && (
            <>
              {" · "}
              <span className="text-foreground">{selection.label}</span> selected
            </>
          )}
        </span>
        <span className="opacity-70">channel {channelId}</span>
      </footer>
    </div>
  );
}

function Legend() {
  const items: Array<{ color: string; label: string }> = [
    { color: KIND_COLORS.channel, label: "Channel hub" },
    { color: KIND_COLORS.wiki_overview, label: "Overview" },
    { color: KIND_COLORS.wiki_topic, label: "Topic" },
    { color: KIND_COLORS.wiki_subtopic, label: "Sub-topic" },
    { color: KIND_COLORS.wiki_decisions, label: "Decisions" },
    { color: KIND_COLORS.wiki_faq, label: "FAQ" },
    { color: KIND_COLORS.entity, label: "Entity" },
  ];
  return (
    <div className="ml-auto flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

interface WikiGraphPanelProps {
  channelId?: string;
  selection: WikiGraphSelectionData;
  onClose: () => void;
}

function WikiGraphPanel({ channelId, selection, onClose }: WikiGraphPanelProps) {
  const navigate = useNavigate();
  // Fetch the full page content when a wiki node is selected so the
  // panel renders the actual markdown — operators don't have to click
  // through to read it. Channel hub + entities don't have backing
  // wiki pages, so they get the lightweight summary view below.
  const wantsPageFetch = !selection.isChannel && !selection.isEntity && !!selection.pageId;
  const {
    data: page,
    isLoading: isPageLoading,
  } = useWikiPage(
    wantsPageFetch ? channelId : undefined,
    wantsPageFetch ? selection.pageId : undefined,
  );
  const goToWikiPage = () => {
    if (!channelId || !selection.pageId) return;
    // Navigate to the channel wiki tab with the selected page in the
    // query param. WikiTab consumes ``?page={pageId}`` and points
    // ``activePageId`` at it on mount.
    navigate(
      `/channels/${channelId}/wiki?page=${encodeURIComponent(selection.pageId)}`,
    );
  };

  // The panel widens when a full page renders so long-form markdown
  // doesn't wrap awkwardly. Channel hub / entity / brief preview keep
  // the narrow 320px form.
  const wide = wantsPageFetch && (page || isPageLoading);
  const widthClass = wide ? "w-[28rem] lg:w-[34rem]" : "w-80";

  return (
    <aside
      className={`${widthClass} shrink-0 border-l border-border bg-card/95 overflow-y-auto shadow-2xl backdrop-blur-sm`}
      role="complementary"
      aria-label="Wiki graph node details"
      data-testid="wiki-graph-panel"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card/95 px-4 py-3 backdrop-blur-sm">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {selection.isChannel
            ? "Channel hub"
            : selection.isEntity
              ? "Entity"
              : "Wiki page"}
        </span>
        <div className="flex items-center gap-1">
          {!selection.isChannel && !selection.isEntity && selection.pageId && (
            <button
              type="button"
              onClick={goToWikiPage}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90"
              aria-label="Open in Wiki tab"
              title="Open this page in the wiki tab (or double-click the node)"
            >
              <ExternalLink size={11} />
              Open in Wiki
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close preview"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="space-y-3 px-4 py-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground leading-tight">
            {selection.label}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {selection.sectionNumber && (
              <span>§{selection.sectionNumber}</span>
            )}
            {selection.pageKind && !selection.isChannel && !selection.isEntity && (
              <span className="capitalize">{selection.pageKind}</span>
            )}
            {typeof selection.memoryCount === "number" && selection.memoryCount > 0 && (
              <span>{selection.memoryCount} memories</span>
            )}
            {selection.lastUpdated && (
              <span title={selection.lastUpdated}>
                Updated {new Date(selection.lastUpdated).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        {/* Full page render. Previously wrapped in
            ``transition-opacity ${isRevalidating ? "opacity-60" : "opacity-100"}``
            but ``isRevalidating`` flips on every poll regardless of
            whether content changed, so the wrapper produced a periodic
            flash. The ``last_updated`` guard in ``useWikiPage`` already
            prevents content tearing — render directly. */}
        {wantsPageFetch && (
          <div data-testid="wiki-graph-panel-content">
            {isPageLoading && (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 size={14} className="animate-spin" />
                Loading page…
              </div>
            )}
            {!isPageLoading && page && page.content && (
              <div className="prose prose-sm dark:prose-invert max-w-none [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-xs">
                <WikiMarkdown
                  content={page.content}
                  citations={page.citations ?? []}
                />
              </div>
            )}
            {!isPageLoading && !page && selection.summary && (
              <p className="text-sm text-foreground/80 leading-relaxed">
                {selection.summary}
              </p>
            )}
            {!isPageLoading && !page && !selection.summary && (
              <p className="text-xs text-muted-foreground italic">
                Page content unavailable. Try the Wiki tab for the latest
                version.
              </p>
            )}
          </div>
        )}

        {/* Channel hub + entities — show summary only. */}
        {!wantsPageFetch && selection.summary && (
          <p className="text-sm text-foreground/80 leading-relaxed">
            {selection.summary}
          </p>
        )}
      </div>
    </aside>
  );
}

export default WikiGraph;
