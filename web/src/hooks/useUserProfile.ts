import { useState, useCallback, useEffect } from "react";

export interface UserProfile {
  displayName: string;
  jobTitle: string;
  avatarColor: string; // hsl string for avatar background
  avatarEmoji: string; // emoji character for user avatar
  onboardingComplete: boolean;
}

const STORAGE_KEY = "beever_user_profile";

export const AVATAR_COLORS = [
  { hsl: "hsl(215, 80%, 55%)", label: "Ocean" },
  { hsl: "hsl(200, 90%, 45%)", label: "Sky" },
  { hsl: "hsl(190, 75%, 45%)", label: "Teal" },
  { hsl: "hsl(160, 60%, 42%)", label: "Forest" },
  { hsl: "hsl(130, 50%, 50%)", label: "Moss" },
  { hsl: "hsl(90, 60%, 45%)", label: "Apple" },

  { hsl: "hsl(45, 95%, 50%)", label: "Gold" },
  { hsl: "hsl(32, 85%, 52%)", label: "Amber" },
  { hsl: "hsl(15, 85%, 60%)", label: "Coral" },
  { hsl: "hsl(0, 75%, 60%)", label: "Crimson" },
  { hsl: "hsl(340, 75%, 52%)", label: "Rose" },
  { hsl: "hsl(320, 65%, 55%)", label: "Magenta" },

  { hsl: "hsl(285, 60%, 55%)", label: "Purple" },
  { hsl: "hsl(260, 70%, 58%)", label: "Violet" },
  { hsl: "hsl(245, 65%, 60%)", label: "Indigo" },
  { hsl: "hsl(230, 25%, 35%)", label: "Slate" },
  { hsl: "hsl(20, 20%, 40%)", label: "Coffee" },
  { hsl: "hsl(0, 0%, 50%)", label: "Silver" },
];

function randomColor() {
  return AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)].hsl;
}

function loadProfile(): UserProfile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as UserProfile;
  } catch {
    // ignore
  }
  return {
    displayName: "",
    jobTitle: "",
    avatarColor: randomColor(),
    avatarEmoji: "🦫",
    onboardingComplete: false,
  };
}

export function useUserProfile() {
  const [profile, setProfileState] = useState<UserProfile>(loadProfile);

  const saveProfile = useCallback((updates: Partial<UserProfile>) => {
    setProfileState((prev) => {
      const next = { ...prev, ...updates };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
    // Dispatch event asynchronously so all listeners (including self) update cleanly
    setTimeout(() => {
      window.dispatchEvent(new Event("beever_profile_updated"));
    }, 0);
  }, []);

  useEffect(() => {
    const handleUpdate = () => {
      setProfileState(loadProfile());
    };
    window.addEventListener("beever_profile_updated", handleUpdate);
    return () => {
      window.removeEventListener("beever_profile_updated", handleUpdate);
    };
  }, []);

  const getGreeting = useCallback(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }, []);

  const getInitials = useCallback((name: string) => {
    return name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join("");
  }, []);

  return { profile, saveProfile, getGreeting, getInitials };
}
