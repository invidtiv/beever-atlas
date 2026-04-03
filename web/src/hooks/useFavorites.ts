import { useState, useEffect, useCallback } from "react";
import type { FavoriteChannel } from "@/lib/types";

const STORAGE_KEY = "beever-favorites";
const MAX_FAVORITES = 50;

function readFavorites(): FavoriteChannel[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeFavorites(favorites: FavoriteChannel[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  } catch {
    // Safari private browsing or quota exceeded — silently fail
  }
}

export interface UseFavoritesReturn {
  favorites: FavoriteChannel[];
  isFavorite: (channelId: string) => boolean;
  toggleFavorite: (channel: FavoriteChannel) => void;
  clearFavorites: () => void;
}

export function useFavorites(): UseFavoritesReturn {
  const [favorites, setFavorites] = useState<FavoriteChannel[]>(readFavorites);

  // Sync across tabs
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setFavorites(readFavorites());
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  const isFavorite = useCallback(
    (channelId: string) => favorites.some((f) => f.channel_id === channelId),
    [favorites],
  );

  const toggleFavorite = useCallback((channel: FavoriteChannel) => {
    setFavorites((prev) => {
      const exists = prev.some((f) => f.channel_id === channel.channel_id);
      const next = exists
        ? prev.filter((f) => f.channel_id !== channel.channel_id)
        : prev.length >= MAX_FAVORITES
          ? prev
          : [...prev, channel];
      writeFavorites(next);
      return next;
    });
  }, []);

  const clearFavorites = useCallback(() => {
    setFavorites([]);
    writeFavorites([]);
  }, []);

  return { favorites, isFavorite, toggleFavorite, clearFavorites };
}
