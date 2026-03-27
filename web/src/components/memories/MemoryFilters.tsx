import type { MemoryFilters as Filters } from "@/hooks/useMemories";

interface MemoryFiltersProps {
  filters: Filters;
  setFilters: (filters: Filters) => void;
}

export function MemoryFilters({ filters, setFilters }: MemoryFiltersProps) {
  function update(key: keyof Filters, value: string) {
    setFilters({ ...filters, [key]: value });
  }

  return (
    <div className="flex flex-wrap gap-3 items-end">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Topic</label>
        <input
          type="text"
          value={filters.topic}
          onChange={(e) => update("topic", e.target.value)}
          placeholder="Filter by topic..."
          className="px-2.5 py-1.5 text-sm rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-40"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Entity</label>
        <input
          type="text"
          value={filters.entity}
          onChange={(e) => update("entity", e.target.value)}
          placeholder="Search entities..."
          className="px-2.5 py-1.5 text-sm rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-40"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">
          Min Importance
        </label>
        <select
          value={filters.minImportance}
          onChange={(e) => update("minImportance", e.target.value)}
          className="px-2.5 py-1.5 text-sm rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        >
          <option value="">All</option>
          <option value="low">Low+</option>
          <option value="medium">Medium+</option>
          <option value="high">High+</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {(filters.topic || filters.entity || filters.minImportance) && (
        <button
          onClick={() => setFilters({ topic: "", entity: "", minImportance: "", dateFrom: "", dateTo: "" })}
          className="px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md hover:bg-slate-50"
        >
          Clear
        </button>
      )}
    </div>
  );
}
