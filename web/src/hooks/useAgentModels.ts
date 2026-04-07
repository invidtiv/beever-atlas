import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { AgentModelConfig, AvailableModels, ModelPreset } from "@/lib/types";

export function useAgentModels() {
  const [config, setConfig] = useState<AgentModelConfig | null>(null);
  const [available, setAvailable] = useState<AvailableModels | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [cfg, avail] = await Promise.all([
        api.get<AgentModelConfig>("/api/settings/models"),
        api.get<AvailableModels>("/api/settings/models/available"),
      ]);
      setConfig(cfg);
      setAvailable(avail);
    } catch (err: any) {
      setError(err.message || "Failed to fetch model config");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateModels = useCallback(async (models: Record<string, string>) => {
    setError(null);
    try {
      const data = await api.put<AgentModelConfig>("/api/settings/models", { models });
      setConfig(data);
      return data;
    } catch (err: any) {
      setError(err.message || "Failed to update models");
      throw err;
    }
  }, []);

  const applyPreset = useCallback(async (preset: ModelPreset) => {
    setError(null);
    try {
      const data = await api.post<AgentModelConfig>("/api/settings/models/preset", { preset });
      setConfig(data);
      return data;
    } catch (err: any) {
      setError(err.message || "Failed to apply preset");
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    models: config?.models ?? {},
    defaults: config?.defaults ?? {},
    availableModels: available,
    ollamaConnected: available?.ollama_connected ?? false,
    isLoading,
    error,
    updateModels,
    applyPreset,
    refetch: fetchAll,
  };
}
