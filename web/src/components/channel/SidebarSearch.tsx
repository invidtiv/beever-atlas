import { Search, X } from "lucide-react";

interface SidebarSearchProps {
  value: string;
  onChange: (value: string) => void;
}

export function SidebarSearch({ value, onChange }: SidebarSearchProps) {
  return (
    <div className="relative px-2 pb-2">
      <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
      <input
        type="text"
        placeholder="Find a channel..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full pl-8 pr-7 py-1.5 rounded-lg bg-muted/50 border border-transparent text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/30 focus:bg-muted transition-colors"
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-muted-foreground/10 text-muted-foreground"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
