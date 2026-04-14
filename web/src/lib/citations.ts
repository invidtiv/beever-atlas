import type {
  Citation,
  CitationEnvelope,
  CitationRef,
  MessageCitations,
  Source,
  SourceKind,
} from "@/types/askTypes";

/**
 * Matches a single source-block line emitted by the LLM in the QA prompt's
 * legacy CITATION_FORMAT. Both leading tokens are observed in practice:
 * "Author:" is the documented form, "Channel:" appears when the LLM leads
 * with channel metadata.
 */
const SOURCE_LINE_RE = /^\s*\[(\d+)\]\s+(Author|Channel|Time):/;

/**
 * Parse a single source-block line into a partial Citation. Exported for tests.
 */
export function parseSourceLine(line: string): Partial<Citation> & { number?: string } | null {
  const numMatch = line.match(/^\s*\[(\d+)\]\s*(.*)$/);
  if (!numMatch) return null;
  const rest = numMatch[2];

  const author = rest.match(/Author:\s*([^|]+)/i);
  const channel = rest.match(/Channel:\s*([^|]+)/i);
  const timestamp = rest.match(/Time:\s*([^|]+)/i);

  return {
    number: numMatch[1],
    text: line.trim(),
    type: "channel_fact",
    author: author ? author[1].trim() : "",
    channel: channel ? channel[1].trim() : "",
    timestamp: timestamp ? timestamp[1].trim() : "",
  };
}

/**
 * Strip the trailing `[N] Author: ... | Channel: ... | Time: ...` block that
 * the backend LLM prompt currently appends to answers. Walks from the end
 * backward to find a contiguous terminal run of source-block lines.
 *
 * Returns both the stripped body and a client-side parsed fallback so we
 * never lose citation data when the server regex parser produced nothing.
 */
export function stripSourcesBlock(content: string): {
  body: string;
  strippedCitations: Citation[];
} {
  if (!content) return { body: content, strippedCitations: [] };

  const lines = content.split("\n");
  let end = lines.length;
  // Skip trailing blank lines.
  while (end > 0 && lines[end - 1].trim() === "") end -= 1;

  let start = end;
  while (start > 0 && SOURCE_LINE_RE.test(lines[start - 1])) start -= 1;

  if (start === end) return { body: content, strippedCitations: [] };

  const parsed: Citation[] = [];
  for (let i = start; i < end; i += 1) {
    const p = parseSourceLine(lines[i]);
    if (p && (p.author || p.channel)) {
      parsed.push({
        type: p.type ?? "channel_fact",
        text: p.text ?? lines[i],
        author: p.author,
        channel: p.channel,
        timestamp: p.timestamp,
      });
    }
  }

  const body = lines.slice(0, start).join("\n").replace(/\s+$/, "");
  return { body, strippedCitations: parsed };
}

const UNAVAILABLE = new Set([
  "",
  "(unavailable)",
  "unavailable",
  "n/a",
  "na",
  "none",
  "null",
  "undefined",
]);

/**
 * Normalize a display string by stripping common UI prefixes (`#`, `@`)
 * and whitespace, then testing against the sentinel set. Used so that
 * values like `"# (unavailable)"` or `"@(unavailable)"` — which can arise
 * when components concat a prefix before checking the value — don't
 * sneak through the plain sentinel filter.
 */
export function looksUnavailable(raw: unknown): boolean {
  if (typeof raw !== "string") return true;
  const stripped = raw
    .replace(/^[#@\s]+/, "")
    .replace(/\s+$/, "")
    .toLowerCase();
  return UNAVAILABLE.has(stripped);
}

/**
 * Return the timestamp to display, or null if the raw value is a known
 * unavailable-ish marker. Callers render nothing when null.
 */
export function displayTimestamp(c: Citation): string | null {
  const raw = (c.timestamp ?? "").trim();
  if (!raw || looksUnavailable(raw)) return null;
  return raw;
}

/** Prefix `@` only when missing; never doubled. */
export function displayAuthor(c: Citation): string | null {
  const raw = (c.author ?? "").trim();
  if (!raw) return null;
  return raw.startsWith("@") ? raw : `@${raw}`;
}

/** Prefix `#` only when missing; never doubled. Strip inner whitespace. */
export function displayChannel(c: Citation): string | null {
  const raw = (c.channel ?? "").trim();
  if (!raw) return null;
  const clean = raw.replace(/\s+/g, "");
  return clean.startsWith("#") ? clean : `#${clean}`;
}

/** Render `permalink` as an anchor only when it's an actual http(s) URL. */
export function displayPermalink(c: Citation): string | null {
  const raw = (c.permalink ?? "").trim();
  if (!/^https?:\/\//i.test(raw)) return null;
  return raw;
}

/**
 * Filter out citations with no useful content. The backend parser can emit
 * rows with only a number captured — don't render those.
 */
export function normalizeCitations(citations: Citation[] | undefined): Citation[] {
  if (!citations) return [];
  return citations.filter((c) => {
    const hasAnything =
      (c.author && c.author.trim()) ||
      (c.channel && c.channel.trim()) ||
      (c.text && c.text.trim());
    return Boolean(hasAnything);
  });
}

// ----- Phase 2 unified selector -----

export interface SelectedCitations {
  /** Structured sources if the envelope has any; otherwise synthesized. */
  sources: Source[];
  /** Structured refs if the envelope has any; otherwise synthesized with marker = index+1. */
  refs: CitationRef[];
  /** Flat legacy-shape citations for components that still render the old card. */
  flat: Citation[];
  /** Whether the envelope included structured data (vs. only legacy items). */
  structured: boolean;
}

/**
 * Collapse either regime (envelope or legacy-flat list) into a consistent
 * `{sources, refs, flat, structured}` shape. Also absorbs a Phase 0
 * content-tail fallback passed as `strippedCitations`.
 */
export function selectCitations(
  citations: MessageCitations | undefined,
  strippedFallback: Citation[] = [],
): SelectedCitations {
  // 1) Envelope with real structured data.
  if (
    citations &&
    !Array.isArray(citations) &&
    Array.isArray(citations.sources) &&
    citations.sources.length > 0
  ) {
    const env = citations as CitationEnvelope;
    return {
      sources: env.sources,
      refs: env.refs ?? [],
      flat: normalizeCitations(env.items),
      structured: true,
    };
  }

  // 2) Envelope with only legacy items (Phase 1 flag-off shape).
  if (citations && !Array.isArray(citations) && Array.isArray(citations.items)) {
    const env = citations as CitationEnvelope;
    const flat = normalizeCitations(env.items);
    return {
      sources: flat.map(flatToSource),
      refs: flat.map((_, i) => ({
        marker: i + 1,
        source_id: `legacy_${i + 1}`,
        inline: false,
      })),
      flat,
      structured: false,
    };
  }

  // 3) Bare legacy list.
  if (Array.isArray(citations) && citations.length > 0) {
    const flat = normalizeCitations(citations);
    return {
      sources: flat.map(flatToSource),
      refs: flat.map((_, i) => ({
        marker: i + 1,
        source_id: `legacy_${i + 1}`,
        inline: false,
      })),
      flat,
      structured: false,
    };
  }

  // 4) Fallback to Phase 0 stripper output.
  if (strippedFallback.length > 0) {
    const flat = normalizeCitations(strippedFallback);
    return {
      sources: flat.map(flatToSource),
      refs: flat.map((_, i) => ({
        marker: i + 1,
        source_id: `legacy_${i + 1}`,
        inline: false,
      })),
      flat,
      structured: false,
    };
  }

  return { sources: [], refs: [], flat: [], structured: false };
}

function flatToSource(c: Citation, i: number): Source {
  const kind = (c.type as SourceKind) || "channel_message";
  return {
    id: `legacy_${i + 1}`,
    kind,
    title: c.author ? `${c.author}${c.channel ? ` in #${c.channel.replace(/^#/, "")}` : ""}` : "Source",
    excerpt: c.text ?? "",
    retrieved_by: {},
    native: {
      author: c.author,
      channel_name: c.channel,
      timestamp: c.timestamp,
    },
    attachments: [],
    permalink: c.permalink && /^https?:\/\//i.test(c.permalink) ? c.permalink : null,
  };
}

/** Group refs by `source_id` — used for "Cited Nx" dedup badges. */
export function groupRefsBySource(
  refs: CitationRef[],
): Map<string, CitationRef[]> {
  const out = new Map<string, CitationRef[]>();
  for (const ref of refs) {
    const list = out.get(ref.source_id) ?? [];
    list.push(ref);
    out.set(ref.source_id, list);
  }
  return out;
}

/** Return the source referenced by a given `[N]` marker, or undefined. */
export function sourceForMarker(
  n: number,
  sources: Source[],
  refs: CitationRef[],
): { source: Source; ref: CitationRef } | undefined {
  const ref = refs.find((r) => r.marker === n);
  if (!ref) return undefined;
  const source = sources.find((s) => s.id === ref.source_id);
  if (!source) return undefined;
  return { source, ref };
}
