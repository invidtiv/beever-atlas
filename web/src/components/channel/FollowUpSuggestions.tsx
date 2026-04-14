interface FollowUpSuggestionsProps {
  suggestions: string[];
  onSelect?: (question: string) => void;
}

export function FollowUpSuggestions({ suggestions, onSelect }: FollowUpSuggestionsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {suggestions.map((q, i) => (
        <button
          key={i}
          onClick={() => onSelect?.(q)}
          className="px-3 py-1.5 text-xs text-muted-foreground bg-card rounded-xl hover:bg-muted hover:text-foreground/90 border border-border transition-colors"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
