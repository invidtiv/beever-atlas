/** Narrative Article module — renders a multi-section article body.
 *
 *  Shape (set by `wiki/modules/narrative_article.py::build_narrative_article_data`):
 *    - sections: array of { anchor, heading, paragraphs[], citations[],
 *                          visual?: { kind, content }, citation_coverage }
 *    - paragraphs[i]: { text, citations[], is_inference }
 *
 *  Layout: article reading column (max-w-prose), section anchor headers,
 *  paragraph styling (leading-relaxed, gap between paragraphs), inline
 *  citation chips, optional supporting visual per section.
 *
 *  This is the new spotlight when present — `ModuleRenderer` renders it
 *  FIRST and demotes the existing 26 modules to a "Reference & Evidence"
 *  appendix below. When `sections` is empty, the component renders
 *  nothing so the page falls back to module-only layout.
 */

import { Fragment, type ReactNode } from "react";
import type { WikiCitation } from "@/lib/types";
import type { ModuleProps } from "./ModuleRenderer";
import { MermaidBlock } from "../MermaidBlock";
import { CalloutBox } from "../CalloutBox";

// ---------------------------------------------------------------------------
// Data shape
// ---------------------------------------------------------------------------

interface NarrativeParagraph {
  text: string;
  citations: string[];
  is_inference: boolean;
}

type VisualKind =
  | "table"
  | "mermaid"
  | "list"
  | "callout"
  | "code"
  | "blockquote";

interface NarrativeVisual {
  kind: VisualKind;
  content: unknown;
}

interface NarrativeSection {
  anchor: string;
  heading: string;
  paragraphs: NarrativeParagraph[];
  citations: string[];
  visual: NarrativeVisual | null;
  citation_coverage: number;
}

interface NarrativeArticleData {
  label?: string;
  renderer_kind?: string;
  sections?: NarrativeSection[];
  total_words?: number;
  distinct_facts_cited?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Coerce a section payload from the unknown ``module.data`` blob. */
function coerceSection(raw: unknown): NarrativeSection | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const anchor = typeof r.anchor === "string" ? r.anchor : "";
  const heading = typeof r.heading === "string" ? r.heading : "";
  if (!anchor || !heading) return null;

  const paragraphsRaw = Array.isArray(r.paragraphs) ? r.paragraphs : [];
  const paragraphs: NarrativeParagraph[] = [];
  for (const p of paragraphsRaw) {
    if (!p || typeof p !== "object") continue;
    const pr = p as Record<string, unknown>;
    const text = typeof pr.text === "string" ? pr.text : "";
    if (!text) continue;
    const citationsRaw = Array.isArray(pr.citations) ? pr.citations : [];
    const citations = citationsRaw
      .filter((c): c is string => typeof c === "string" && c.length > 0);
    paragraphs.push({
      text,
      citations,
      is_inference: Boolean(pr.is_inference),
    });
  }
  if (paragraphs.length === 0) return null;

  const citationsRaw = Array.isArray(r.citations) ? r.citations : [];
  const citations = citationsRaw
    .filter((c): c is string => typeof c === "string" && c.length > 0);

  let visual: NarrativeVisual | null = null;
  if (r.visual && typeof r.visual === "object") {
    const vr = r.visual as Record<string, unknown>;
    const kindRaw = typeof vr.kind === "string" ? vr.kind.toLowerCase() : "";
    const allowed: VisualKind[] = [
      "table",
      "mermaid",
      "list",
      "callout",
      "code",
      "blockquote",
    ];
    if ((allowed as string[]).includes(kindRaw)) {
      visual = { kind: kindRaw as VisualKind, content: vr.content };
    }
  }

  const coverage =
    typeof r.citation_coverage === "number" ? r.citation_coverage : 0;

  return {
    anchor,
    heading,
    paragraphs,
    citations,
    visual,
    citation_coverage: coverage,
  };
}

/** Build a Map from fact_id → 1-indexed display number based on the
 *  order of first occurrence across all sections. The frontend uses
 *  this map so chips render as `[1]`, `[2]` etc. with stable indices.
 */
function buildFactIdIndex(sections: NarrativeSection[]): Map<string, number> {
  const idx = new Map<string, number>();
  for (const section of sections) {
    for (const p of section.paragraphs) {
      for (const cid of p.citations) {
        if (!idx.has(cid)) {
          idx.set(cid, idx.size + 1);
        }
      }
    }
  }
  return idx;
}

/** Total word count across every paragraph (for the reading-time chip). */
function totalWordCount(sections: NarrativeSection[]): number {
  let total = 0;
  for (const section of sections) {
    for (const p of section.paragraphs) {
      total += p.text.trim().split(/\s+/).filter(Boolean).length;
    }
  }
  return total;
}

/** Reading-time estimate (200 wpm, rounded up to nearest minute). */
function readingTimeMinutes(words: number): number {
  if (words <= 0) return 0;
  return Math.max(1, Math.ceil(words / 200));
}

/** Distinct fact_ids cited across the article. */
function distinctFactCount(sections: NarrativeSection[]): number {
  const seen = new Set<string>();
  for (const section of sections) {
    for (const p of section.paragraphs) {
      for (const cid of p.citations) seen.add(cid);
    }
  }
  return seen.size;
}

// ---------------------------------------------------------------------------
// Inline citation chip (with hover preview)
// ---------------------------------------------------------------------------

interface CitationChipProps {
  factId: string;
  displayIndex: number;
  citation?: WikiCitation;
}

function CitationChip({ factId, displayIndex, citation }: CitationChipProps) {
  // Build a native ``title`` string as a zero-cost fallback so the
  // cited fact is reachable even when the popover is not shown
  // (mobile, screen readers, etc.).
  const titleParts: string[] = [];
  if (citation?.text_excerpt) titleParts.push(citation.text_excerpt);
  if (citation?.author) titleParts.push(`— @${citation.author}`);
  if (citation?.timestamp) titleParts.push(citation.timestamp);
  const titleText = titleParts.join(" ");

  return (
    <span className="group/cite relative inline-block align-baseline">
      <button
        type="button"
        data-fact-id={factId}
        data-testid="narrative-citation-chip"
        title={titleText || undefined}
        className="inline-flex items-center px-1 py-0.5 mx-0.5 text-[10px] font-medium leading-none rounded bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      >
        [{displayIndex}]
      </button>
      {citation && (
        <span
          role="tooltip"
          data-testid="narrative-citation-popover"
          className="pointer-events-none invisible group-hover/cite:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 max-w-[calc(100vw-2rem)] rounded-lg bg-popover border border-border px-3 py-2.5 text-xs text-popover-foreground shadow-xl z-50"
        >
          <div className="flex items-center gap-2 mb-1.5">
            {citation.author && (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                @{citation.author}
              </span>
            )}
            {citation.timestamp && (
              <span className="text-muted-foreground text-[10px]">
                {citation.timestamp}
              </span>
            )}
          </div>
          <p className="text-popover-foreground/90 leading-relaxed line-clamp-3">
            {citation.text_excerpt}
          </p>
        </span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Visual dispatcher
// ---------------------------------------------------------------------------

interface VisualBlockProps {
  visual: NarrativeVisual;
}

function VisualBlock({ visual }: VisualBlockProps) {
  switch (visual.kind) {
    case "table": {
      const content = visual.content as
        | { headers?: unknown; rows?: unknown }
        | undefined
        | null;
      const headers = Array.isArray(content?.headers)
        ? (content!.headers as unknown[]).map((h) => String(h))
        : [];
      const rowsRaw = Array.isArray(content?.rows) ? (content!.rows as unknown[]) : [];
      const rows: string[][] = rowsRaw.map((row) =>
        Array.isArray(row)
          ? (row as unknown[]).map((cell) => String(cell))
          : [],
      );
      if (headers.length === 0 && rows.length === 0) return null;
      return (
        <div
          className="my-4 overflow-x-auto"
          data-testid="narrative-visual-table"
        >
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                {headers.map((h, i) => (
                  <th
                    key={i}
                    scope="col"
                    className="text-left font-semibold px-3 py-2 text-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/50">
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="px-3 py-2 text-muted-foreground align-top"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    case "mermaid": {
      const chart = typeof visual.content === "string" ? visual.content : "";
      if (!chart) return null;
      return (
        <div data-testid="narrative-visual-mermaid">
          <MermaidBlock chart={chart} />
        </div>
      );
    }
    case "list": {
      const content = visual.content as
        | { items?: unknown; ordered?: unknown }
        | undefined
        | null;
      const itemsRaw = Array.isArray(content?.items)
        ? (content!.items as unknown[])
        : [];
      const items = itemsRaw.map((item) => String(item)).filter(Boolean);
      if (items.length === 0) return null;
      const ordered = Boolean(content?.ordered);
      const ListTag = ordered ? "ol" : "ul";
      return (
        <ListTag
          data-testid="narrative-visual-list"
          className={`my-4 ${ordered ? "list-decimal" : "list-disc"} pl-6 space-y-1.5 text-sm text-foreground`}
        >
          {items.map((item, i) => (
            <li key={i} className="leading-relaxed">
              {item}
            </li>
          ))}
        </ListTag>
      );
    }
    case "callout": {
      const content = visual.content as
        | { type?: unknown; content?: unknown; text?: unknown }
        | undefined
        | null;
      const typeRaw =
        typeof content?.type === "string" ? content.type.toLowerCase() : "note";
      const type: "note" | "tip" | "warning" =
        typeRaw === "tip" || typeRaw === "warning" ? typeRaw : "note";
      const text =
        typeof content?.content === "string"
          ? content.content
          : typeof content?.text === "string"
            ? content.text
            : "";
      if (!text) return null;
      return (
        <div data-testid="narrative-visual-callout">
          <CalloutBox type={type} content={text} />
        </div>
      );
    }
    case "code": {
      const content = visual.content as
        | { language?: unknown; code?: unknown; content?: unknown }
        | string
        | undefined
        | null;
      const code =
        typeof content === "string"
          ? content
          : typeof content?.code === "string"
            ? content.code
            : typeof content?.content === "string"
              ? content.content
              : "";
      if (!code) return null;
      const language =
        typeof content === "object" && content && typeof content.language === "string"
          ? content.language
          : "";
      return (
        <pre
          data-testid="narrative-visual-code"
          className="my-4 p-4 rounded-lg bg-muted/40 border border-border overflow-x-auto text-xs"
        >
          <code className={language ? `language-${language}` : undefined}>
            {code}
          </code>
        </pre>
      );
    }
    case "blockquote": {
      const content = visual.content as
        | { content?: unknown; text?: unknown; attribution?: unknown }
        | string
        | undefined
        | null;
      const text =
        typeof content === "string"
          ? content
          : typeof content?.content === "string"
            ? content.content
            : typeof content?.text === "string"
              ? content.text
              : "";
      if (!text) return null;
      const attribution =
        typeof content === "object" && content && typeof content.attribution === "string"
          ? content.attribution
          : "";
      return (
        <blockquote
          data-testid="narrative-visual-blockquote"
          className="my-4 border-l-4 border-muted pl-4 italic text-muted-foreground"
        >
          <p className="text-sm leading-relaxed">{text}</p>
          {attribution && (
            <footer className="mt-1 text-xs not-italic text-muted-foreground/70">
              — {attribution}
            </footer>
          )}
        </blockquote>
      );
    }
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Paragraph renderer (with inline citation chip injection)
// ---------------------------------------------------------------------------

interface ParagraphProps {
  paragraph: NarrativeParagraph;
  factIdIndex: Map<string, number>;
  citationLookup: Map<string, WikiCitation>;
}

/** Render the paragraph text with one trailing chip per citation. The
 *  v3 prompt does not embed `[f_xxx]` placeholders inside the text
 *  body — citations live in the structured `paragraph.citations`
 *  array. We render the prose as-is and append the chips at the end
 *  of the paragraph (Wikipedia-footnote style).
 */
function ParagraphLine({ paragraph, factIdIndex, citationLookup }: ParagraphProps) {
  const chips: ReactNode[] = paragraph.citations.map((cid) => {
    const displayIndex = factIdIndex.get(cid);
    if (!displayIndex) return null;
    return (
      <CitationChip
        key={cid}
        factId={cid}
        displayIndex={displayIndex}
        citation={citationLookup.get(cid)}
      />
    );
  });

  return (
    <p
      data-testid="narrative-paragraph"
      data-is-inference={paragraph.is_inference ? "true" : "false"}
      className="text-[15px] leading-relaxed text-foreground/90"
    >
      {paragraph.is_inference && (
        <span
          data-testid="narrative-inference-chip"
          className="inline-flex items-center px-1.5 py-0.5 mr-1.5 text-[10px] font-medium rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 align-middle"
        >
          [agent-inference]
        </span>
      )}
      {paragraph.text}
      {chips.length > 0 && (
        <span className="ml-0.5">
          {chips.map((chip, i) => (
            <Fragment key={i}>{chip}</Fragment>
          ))}
        </span>
      )}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function NarrativeArticleModule({ module, citations }: ModuleProps) {
  const data = (module.data ?? {}) as NarrativeArticleData;
  const sectionsRaw = Array.isArray(data.sections) ? data.sections : [];
  const sections: NarrativeSection[] = [];
  for (const raw of sectionsRaw) {
    const cleaned = coerceSection(raw);
    if (cleaned) sections.push(cleaned);
  }
  if (sections.length === 0) {
    return null;
  }

  // Build the fact_id → 1-indexed display number map and the
  // fact_id → WikiCitation lookup.
  const factIdIndex = buildFactIdIndex(sections);
  const citationLookup = new Map<string, WikiCitation>();
  for (const c of citations) {
    if (c?.id) citationLookup.set(c.id, c);
  }

  const words = totalWordCount(sections);
  const minutes = readingTimeMinutes(words);
  const distinctFacts = distinctFactCount(sections);

  return (
    <article
      data-testid="narrative-article"
      id={`module-${module.anchor}`}
      className="mx-auto max-w-prose mt-2 mb-10"
      data-toc-skip
    >
      <header className="mb-6 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {minutes > 0 && (
          <span
            data-testid="narrative-reading-time"
            className="inline-flex items-center gap-1 rounded-md bg-muted/50 px-2 py-1"
          >
            <span aria-hidden="true">⏱</span>
            <span>
              {minutes} min read
            </span>
          </span>
        )}
        {distinctFacts > 0 && (
          <span
            data-testid="narrative-memories-synthesized"
            className="inline-flex items-center gap-1 rounded-md bg-muted/50 px-2 py-1"
          >
            <span aria-hidden="true">🧠</span>
            <span>
              {distinctFacts} {distinctFacts === 1 ? "memory" : "memories"} synthesized
            </span>
          </span>
        )}
      </header>

      {sections.map((section) => (
        <section
          key={section.anchor}
          data-testid="narrative-section"
          className="mb-8 scroll-mt-20"
        >
          <h2
            id={section.anchor}
            data-testid="narrative-section-heading"
            className="text-xl font-semibold text-foreground mb-3 scroll-mt-20"
          >
            {section.heading}
          </h2>
          <div className="space-y-3">
            {section.paragraphs.map((paragraph, i) => (
              <ParagraphLine
                key={i}
                paragraph={paragraph}
                factIdIndex={factIdIndex}
                citationLookup={citationLookup}
              />
            ))}
          </div>
          {section.visual && <VisualBlock visual={section.visual} />}
        </section>
      ))}
    </article>
  );
}
