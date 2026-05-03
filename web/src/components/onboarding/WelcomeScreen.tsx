import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  MessageSquare,
  Monitor,
  Building2,
  MessagesSquare,
  FileText,
  ChevronRight,
  Sparkles,
  Brain,
  Compass,
  Lock,
} from "lucide-react";
import EmojiPicker, { Theme } from "emoji-picker-react";
import type { EmojiClickData } from "emoji-picker-react";
import { cn } from "@/lib/utils";
import { useUserProfile, AVATAR_COLORS } from "@/hooks/useUserProfile";

interface WelcomeScreenProps {
  onConnect: (platform: string) => void;
}

const PLATFORMS: {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  desc: string;
}[] = [
  { key: "slack", label: "Slack", icon: MessageSquare, desc: "Connect a Slack workspace" },
  { key: "discord", label: "Discord", icon: Monitor, desc: "Connect a Discord server" },
  { key: "teams", label: "Teams", icon: Building2, desc: "Connect a Teams tenant" },
  { key: "mattermost", label: "Mattermost", icon: MessagesSquare, desc: "Connect a Mattermost server" },
  { key: "file", label: "File Import", icon: FileText, desc: "Upload a CSV / TSV / JSONL chat export" },
];

// Hero feature copy is OSS-personal-intelligence positioned, NOT
// "your team's second brain". The OSS thesis is "compounding LLM
// wiki for one person"; multi-tenant team features live in the
// enterprise tier and shouldn't lead the open-source onboarding.
const HERO_FEATURES = [
  {
    icon: Brain,
    title: "Compounding memory",
    desc: "Every conversation becomes a fact, decision, or topic — automatically.",
  },
  {
    icon: Compass,
    title: "Living wiki",
    desc: "Pages refresh incrementally so your second brain never goes stale.",
  },
  {
    icon: Lock,
    title: "Yours alone",
    desc: "Local-first. Self-hostable. Your knowledge never leaves your machine.",
  },
];

export function WelcomeScreen({ onConnect }: WelcomeScreenProps) {
  const { profile, saveProfile } = useUserProfile();
  const [step, setStep] = useState<"profile" | "connect">("profile");
  const [nameValue, setNameValue] = useState(profile.displayName || "");
  const [titleValue, setTitleValue] = useState(profile.jobTitle || "");
  const [chosenColor, setChosenColor] = useState(profile.avatarColor || AVATAR_COLORS[0].hsl);
  const [chosenEmoji, setChosenEmoji] = useState(profile.avatarEmoji || "🦫");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const emojiPickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (emojiPickerRef.current && !emojiPickerRef.current.contains(event.target as Node)) {
        setShowEmojiPicker(false);
      }
    }
    if (showEmojiPicker) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showEmojiPicker]);

  // Lock body scroll while the welcome overlay is mounted so the
  // app shell underneath cannot scroll-bleed when the user nudges
  // a trackpad. Restored on unmount.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  function handleProfileContinue() {
    if (!nameValue.trim()) {
      nameInputRef.current?.focus();
      return;
    }
    saveProfile({
      displayName: nameValue.trim(),
      jobTitle: titleValue.trim(),
      avatarColor: chosenColor,
      avatarEmoji: chosenEmoji,
    });
    setStep("connect");
  }

  // Render through a portal to ``document.body`` to escape the
  // AppShell's transform-based route-transition wrapper (App.tsx).
  // ``position: fixed`` creates a new containing block when an
  // ancestor has a ``transform``/``filter`` set, so a
  // ``fixed inset-0`` overlay nested inside AppShell's main area
  // wouldn't actually cover the sidebar/header. Portaling sidesteps
  // the stacking-context trap entirely.
  const overlay = (
    <div className="fixed inset-0 z-[100] h-screen w-screen overflow-hidden bg-background">
      {/* Ambient gradient blobs — pinned to viewport */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute -top-[20%] -left-[10%] h-[60%] w-[60%] rounded-full bg-primary/25 blur-[140px] animate-pulse"
          style={{ animationDuration: "9s" }}
        />
        <div
          className="absolute -bottom-[25%] -right-[10%] h-[60%] w-[60%] rounded-full bg-blue-500/15 blur-[160px] animate-pulse"
          style={{ animationDuration: "11s" }}
        />
        <div
          className="absolute top-[25%] right-[20%] h-[35%] w-[35%] rounded-full bg-teal-500/10 blur-[120px] animate-pulse"
          style={{ animationDuration: "13s" }}
        />
      </div>

      <div className="relative z-10 grid h-full grid-cols-1 lg:grid-cols-[5fr_6fr] xl:grid-cols-[4fr_5fr]">
        {/* ─── Hero panel (desktop only) ─────────────────────────── */}
        <aside className="relative hidden flex-col justify-between overflow-hidden p-10 lg:flex xl:p-14">
          {/* Brand mark */}
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[#18759c] text-primary-foreground shadow-lg shadow-primary/30">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="font-heading text-base font-semibold tracking-tight text-foreground">
              Beever Atlas
            </span>
          </div>

          {/* Tagline + features */}
          <div className="space-y-8">
            <div>
              <h2 className="font-heading text-[40px] font-bold leading-[1.05] tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-foreground via-foreground to-foreground/55 xl:text-[48px]">
                Your personal
                <br />
                intelligence.
              </h2>
              <p className="mt-4 max-w-md text-[14.5px] leading-relaxed text-muted-foreground">
                A compounding LLM wiki that learns from every conversation
                you save — your second brain that never forgets a thing.
              </p>
            </div>

            <ul className="space-y-4">
              {HERO_FEATURES.map(({ icon: Icon, title, desc }) => (
                <li key={title} className="flex items-start gap-3.5">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary shadow-sm">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-[13.5px] font-semibold tracking-tight text-foreground">
                      {title}
                    </p>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">
                      {desc}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-[11.5px] tracking-wide text-muted-foreground/70">
            Open source · Local-first · Self-hostable
          </p>
        </aside>

        {/* ─── Form / connect panel — never scrolls; designed to fit ──── */}
        <main className="flex h-full items-center justify-center overflow-y-auto px-6 py-8 sm:px-10">
          <div className="w-full max-w-md">
            {/* Step pill row */}
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-2 lg:hidden">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[#18759c] text-primary-foreground">
                  <Sparkles className="h-3 w-3" />
                </div>
                <span className="font-heading text-[13px] font-semibold tracking-tight text-foreground">
                  Beever Atlas
                </span>
              </div>

              <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-card/60 px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground backdrop-blur-md">
                Step {step === "profile" ? "1" : "2"} of 2
              </span>
            </div>

            {step === "profile" ? (
              <div className="animate-fade-in">
                {/* Headline — denser to fit in viewport */}
                <div className="mb-5">
                  <h1 className="font-heading text-[28px] font-bold leading-[1.1] tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-foreground to-foreground/60 sm:text-[32px]">
                    Make it yours
                  </h1>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">
                    Pick an avatar and tell us what to call you. Used wherever
                    your activity shows up.
                  </p>
                </div>

                {/* Form card */}
                <div className="space-y-5 rounded-3xl border border-white/10 bg-card/70 p-6 shadow-2xl shadow-black/10 backdrop-blur-2xl dark:border-white/5">
                  {/* Avatar + colors */}
                  <div className="space-y-3.5">
                    <div className="relative flex justify-center">
                      <button
                        type="button"
                        onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                        className="group relative flex h-20 w-20 items-center justify-center rounded-[26px] text-[44px] shadow-2xl transition-all duration-300 hover:scale-[1.04] focus:outline-none focus:ring-4 focus:ring-primary/30"
                        style={{
                          background: chosenColor,
                          boxShadow: `0 14px 40px -8px ${chosenColor}`,
                        }}
                        aria-label="Pick an emoji avatar"
                      >
                        {chosenEmoji}
                        <div className="absolute inset-0 flex items-center justify-center rounded-[26px] bg-black/40 opacity-0 backdrop-blur-[3px] transition-opacity group-hover:opacity-100">
                          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-white">
                            Change
                          </span>
                        </div>
                      </button>

                      {showEmojiPicker && (
                        <div
                          ref={emojiPickerRef}
                          className="custom-emoji-picker absolute left-1/2 top-24 z-50 -translate-x-1/2 rounded-2xl border border-border shadow-2xl"
                        >
                          <EmojiPicker
                            onEmojiClick={(e: EmojiClickData) => {
                              setChosenEmoji(e.emoji);
                              setShowEmojiPicker(false);
                            }}
                            theme={Theme.AUTO}
                            searchPlaceHolder="Search emojis..."
                            width={300}
                            height={360}
                          />
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap justify-center gap-2">
                      {AVATAR_COLORS.map(({ hsl, label }) => (
                        <button
                          key={label}
                          type="button"
                          aria-label={label}
                          onClick={() => setChosenColor(hsl)}
                          className={cn(
                            "h-6 w-6 rounded-full transition-all duration-200 ring-offset-2 ring-offset-card focus:outline-none cursor-pointer",
                            chosenColor === hsl
                              ? "ring-2 ring-foreground scale-110 shadow-md"
                              : "opacity-70 hover:scale-110 hover:opacity-100"
                          )}
                          style={{ background: hsl }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Name */}
                  <div className="space-y-1.5">
                    <label
                      htmlFor="welcome-name"
                      className="pl-1 text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground/80"
                    >
                      Your name <span className="text-primary">*</span>
                    </label>
                    <input
                      id="welcome-name"
                      ref={nameInputRef}
                      type="text"
                      placeholder="e.g. Alex Johnson"
                      value={nameValue}
                      onChange={(e) => setNameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleProfileContinue();
                      }}
                      className={cn(
                        "w-full rounded-xl border border-border/50 bg-background/60 px-4 py-2.5 text-[14px] font-medium text-foreground shadow-inner",
                        "placeholder:font-normal placeholder:text-muted-foreground/40",
                        "focus:border-primary/40 focus:bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/40",
                        "transition-all duration-200"
                      )}
                      autoFocus
                    />
                  </div>

                  {/* Job title */}
                  <div className="space-y-1.5">
                    <label
                      htmlFor="welcome-title"
                      className="pl-1 text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground/80"
                    >
                      Role / Title{" "}
                      <span className="font-normal normal-case tracking-normal text-muted-foreground/40">
                        (optional)
                      </span>
                    </label>
                    <input
                      id="welcome-title"
                      type="text"
                      placeholder="e.g. Engineering Lead"
                      value={titleValue}
                      onChange={(e) => setTitleValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleProfileContinue();
                      }}
                      className={cn(
                        "w-full rounded-xl border border-border/50 bg-background/60 px-4 py-2.5 text-[14px] font-medium text-foreground shadow-inner",
                        "placeholder:font-normal placeholder:text-muted-foreground/40",
                        "focus:border-primary/40 focus:bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/40",
                        "transition-all duration-200"
                      )}
                    />
                  </div>

                  <button
                    type="button"
                    onClick={handleProfileContinue}
                    disabled={!nameValue.trim()}
                    className={cn(
                      "flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-[14px] font-bold tracking-wide shadow-lg",
                      "bg-gradient-to-r from-primary to-[#18759c] text-primary-foreground",
                      "transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_32px_rgba(11,79,108,0.45)]",
                      "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:hover:translate-y-0"
                    )}
                  >
                    Continue
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>

                {/* Step indicator dots */}
                <div className="mt-5 flex justify-center gap-2">
                  <div className="h-1.5 w-9 rounded-full bg-primary shadow-[0_0_8px_rgba(11,79,108,0.5)]" />
                  <div className="h-1.5 w-2 rounded-full bg-border" />
                </div>
              </div>
            ) : (
              <div className="animate-fade-in">
                {/* Personal greeting + avatar */}
                <div className="mb-5">
                  <div className="mb-4 flex items-center gap-3">
                    <div
                      className="flex h-11 w-11 items-center justify-center rounded-2xl text-[28px] shadow-lg"
                      style={{
                        background: chosenColor,
                        boxShadow: `0 10px 26px -6px ${chosenColor}`,
                      }}
                    >
                      {chosenEmoji}
                    </div>
                    <div>
                      <p className="text-[10.5px] font-bold uppercase tracking-widest text-muted-foreground/80">
                        Welcome
                      </p>
                      <p className="text-[14px] font-semibold tracking-tight text-foreground">
                        {nameValue.split(" ")[0]}
                      </p>
                    </div>
                  </div>
                  <h1 className="font-heading text-[26px] font-bold leading-[1.1] tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-foreground to-foreground/60 sm:text-[30px]">
                    Connect your first source
                  </h1>
                  <p className="mt-2 text-[13.5px] leading-relaxed text-muted-foreground">
                    Pick where your conversations live. Beever extracts
                    facts, decisions, and topics automatically.
                  </p>
                </div>

                {/* Platform grid */}
                <div className="rounded-3xl border border-white/10 bg-card/70 p-5 shadow-2xl shadow-black/10 backdrop-blur-2xl dark:border-white/5">
                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {PLATFORMS.map(({ key, label, icon: Icon, desc }) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => onConnect(key)}
                        className={cn(
                          "custom-platform-btn group flex flex-col items-start gap-2 rounded-2xl border border-white/10 p-4 text-left",
                          "bg-background/40 transition-all duration-200 cursor-pointer",
                          "hover:-translate-y-0.5 hover:border-primary/40 hover:bg-background/80 hover:shadow-[0_10px_24px_rgba(0,0,0,0.10)]"
                        )}
                      >
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/15 bg-primary/10 text-primary shadow-sm transition-all duration-200 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground">
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <p className="text-[13.5px] font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
                            {label}
                          </p>
                          <p className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">
                            {desc}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Back + step indicator */}
                <div className="mt-5 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setStep("profile")}
                    className="flex cursor-pointer items-center gap-1 text-[12.5px] font-semibold text-muted-foreground transition-all hover:-translate-x-1 hover:text-foreground"
                  >
                    ← Back
                  </button>
                  <div className="flex gap-2">
                    <div className="h-1.5 w-2 rounded-full bg-border" />
                    <div className="h-1.5 w-9 rounded-full bg-primary shadow-[0_0_8px_rgba(11,79,108,0.5)]" />
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}
