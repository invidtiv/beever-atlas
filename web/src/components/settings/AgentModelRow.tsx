import type { AgentMeta } from "@/lib/agentMeta";

interface Props {
  agent: AgentMeta;
  currentModel: string;
  defaultModel: string;
  availableModels: string[];
  onChange: (agentName: string, model: string) => void;
}

export function AgentModelRow({ agent, currentModel, defaultModel, availableModels, onChange }: Props) {
  const isDefault = currentModel === defaultModel;

  return (
    <div className="flex items-center gap-4 py-2.5 px-1">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-foreground">{agent.displayName}</div>
        <div className="text-xs text-muted-foreground">{agent.description}</div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <select
          value={currentModel}
          onChange={(e) => onChange(agent.name, e.target.value)}
          className="text-xs bg-background border border-border rounded-md px-2 py-1.5 min-w-[200px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <optgroup label="Gemini (Cloud)">
            {availableModels
              .filter((m) => m.startsWith("gemini-"))
              .map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
          </optgroup>
          <optgroup label="Local (Ollama)">
            {availableModels
              .filter((m) => m.startsWith("ollama_chat/"))
              .map((m) => (
                <option key={m} value={m}>{m.replace("ollama_chat/", "")}</option>
              ))}
          </optgroup>
        </select>
        {!isDefault && (
          <button
            onClick={() => onChange(agent.name, defaultModel)}
            className="text-xs text-muted-foreground hover:text-foreground"
            title="Reset to default"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
