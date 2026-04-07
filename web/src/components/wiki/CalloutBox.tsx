interface CalloutBoxProps {
  type: "note" | "tip" | "warning";
  content: string;
}

const styles = {
  note: {
    container: "bg-blue-500/10 border-blue-500/30",
    text: "text-blue-400",
    label: "Note",
  },
  tip: {
    container: "bg-emerald-500/10 border-emerald-500/30",
    text: "text-emerald-400",
    label: "Tip",
  },
  warning: {
    container: "bg-amber-500/10 border-amber-500/30",
    text: "text-amber-400",
    label: "Warning",
  },
};

export function CalloutBox({ type, content }: CalloutBoxProps) {
  const s = styles[type];
  return (
    <div className={`my-3 rounded-lg border ${s.container} p-4`}>
      <p className={`text-sm font-semibold ${s.text}`}>{s.label}</p>
      <p className={`mt-1 text-sm ${s.text} opacity-90`}>{content}</p>
    </div>
  );
}
