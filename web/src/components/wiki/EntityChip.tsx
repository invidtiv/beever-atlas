interface EntityChipProps {
  type: "person" | "topic" | "tech";
  name: string;
  onNavigate?: (pageId: string) => void;
}

const chipStyles = {
  person: "bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 cursor-pointer",
  topic: "bg-indigo-500/15 text-indigo-400",
  tech: "bg-purple-500/15 text-purple-400",
};

export function EntityChip({ type, name, onNavigate }: EntityChipProps) {
  const handleClick = () => {
    if (!onNavigate || type !== "person") return;
    onNavigate("people");
  };

  const isClickable = type === "person" && !!onNavigate;

  return (
    <span
      onClick={isClickable ? handleClick : undefined}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${chipStyles[type]} transition-colors ${isClickable ? "" : "cursor-default"}`}
    >
      {name}
    </span>
  );
}
