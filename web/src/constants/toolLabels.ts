export const TOOL_LABELS: Record<string, string> = {
  get_wiki_page: "Wiki Page Lookup",
  get_topic_overview: "Topic Overview",
  search_qa_history: "Past Q&A Search",
  search_channel_facts: "Channel Facts Search",
  search_media_references: "Media & Links Search",
  get_recent_activity: "Recent Activity",
  search_relationships: "Relationship Graph",
  trace_decision_history: "Decision History",
  find_experts: "Expert Finder",
  search_external_knowledge: "Web Search",
};

export function getToolLabel(toolName: string): string {
  return TOOL_LABELS[toolName] ?? toolName.replace(/_/g, " ");
}

export type ToolCategory = "wiki" | "search" | "graph" | "external";

export const TOOL_CATEGORIES: Record<string, ToolCategory> = {
  get_wiki_page: "wiki",
  get_topic_overview: "wiki",
  search_qa_history: "search",
  search_channel_facts: "search",
  search_media_references: "search",
  get_recent_activity: "search",
  search_relationships: "graph",
  trace_decision_history: "graph",
  find_experts: "graph",
  search_external_knowledge: "external",
};

export const CATEGORY_ICONS: Record<ToolCategory, string> = {
  wiki: "📖",
  search: "🔍",
  graph: "🔗",
  external: "🌐",
};

export const CATEGORY_COLORS: Record<ToolCategory, string> = {
  wiki: "text-blue-400",
  search: "text-amber-400",
  graph: "text-purple-400",
  external: "text-green-400",
};
