import { useState, useRef, useEffect } from "react";
import { User, Pencil, Check, Clock, Palette } from "lucide-react";
import EmojiPicker, { Theme } from "emoji-picker-react";
import type { EmojiClickData } from "emoji-picker-react";
import { useUserProfile, AVATAR_COLORS } from "@/hooks/useUserProfile";
import { cn } from "@/lib/utils";

export function ProfilePage() {
  const { profile, saveProfile, getGreeting } = useUserProfile();
  const [editing, setEditing] = useState(false);
  const [nameValue, setNameValue] = useState(profile.displayName);
  const [titleValue, setTitleValue] = useState(profile.jobTitle);
  const [colorValue, setColorValue] = useState(profile.avatarColor);
  const [emojiValue, setEmojiValue] = useState(profile.avatarEmoji || "🦫");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [saved, setSaved] = useState(false);
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

  function handleSave() {
    saveProfile({
      displayName: nameValue.trim() || profile.displayName,
      jobTitle: titleValue.trim(),
      avatarColor: colorValue,
      avatarEmoji: emojiValue,
    });
    setEditing(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleCancel() {
    setNameValue(profile.displayName);
    setTitleValue(profile.jobTitle);
    setColorValue(profile.avatarColor);
    setEmojiValue(profile.avatarEmoji || "🦫");
    setEditing(false);
    setShowEmojiPicker(false);
  }

  const greeting = getGreeting();
  const hour = new Date().getHours();

  const greetingEmoji = hour < 12 ? "☀️" : hour < 17 ? "🌤" : "🌙";

  return (
    <div className="h-full overflow-auto p-6 sm:p-8 max-w-2xl mx-auto animate-fade-in">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-foreground tracking-tight">
          My Profile
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Personalize how Beever greets and identifies you.
        </p>
      </div>

      {/* Greeting banner */}
      <div className="rounded-2xl bg-gradient-to-br from-primary/15 via-primary/8 to-transparent border border-primary/20 p-6 mb-6 flex items-center gap-5">
        <div className="relative">
          <button
            type="button"
            disabled={!editing}
            onClick={() => setShowEmojiPicker(!showEmojiPicker)}
            className={cn(
              "w-16 h-16 rounded-2xl flex items-center justify-center text-3xl shadow-lg shrink-0 transition-all duration-300",
              editing ? "cursor-pointer hover:scale-105 hover:ring-2 hover:ring-primary/50 relative group" : "cursor-default"
            )}
            style={{ background: editing ? colorValue : profile.avatarColor }}
          >
            {editing ? emojiValue : (profile.avatarEmoji || "🦫")}
            {editing && (
              <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl flex items-center justify-center">
                <span className="text-white text-[10px] font-semibold">Change</span>
              </div>
            )}
          </button>
          
          {showEmojiPicker && editing && (
            <div ref={emojiPickerRef} className="absolute left-0 right-0 sm:right-auto mt-3 z-50 shadow-2xl rounded-xl custom-emoji-picker max-w-[calc(100vw-2rem)]">
              <EmojiPicker
                onEmojiClick={(e: EmojiClickData) => {
                  setEmojiValue(e.emoji);
                  setShowEmojiPicker(false);
                }}
                theme={Theme.AUTO}
                searchPlaceHolder="Search emojis..."
                width={320}
                height={400}
              />
            </div>
          )}
        </div>
        <div>
          <p className="text-base text-muted-foreground">
            {greetingEmoji} {greeting},{" "}
          </p>
          <h2 className="font-heading text-2xl text-foreground tracking-tight">
            {profile.displayName || "there"}
          </h2>
          {profile.jobTitle && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {profile.jobTitle}
            </p>
          )}
        </div>
      </div>

      {/* Profile card */}
      <div className="rounded-2xl border border-border bg-card overflow-hidden">
        {/* Card header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-semibold text-foreground">
              Profile Details
            </span>
          </div>
          {!editing ? (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCancel}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted transition-colors text-muted-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Check className="w-3.5 h-3.5" />
                Save changes
              </button>
            </div>
          )}
        </div>

        {/* Fields */}
        <div className="p-6 space-y-5">
          {/* Display Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">
              Display Name
            </label>
            {editing ? (
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                autoFocus
                className="w-full px-4 py-2.5 rounded-xl border bg-background text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
              />
            ) : (
              <p className="text-sm text-foreground font-medium">
                {profile.displayName || (
                  <span className="text-muted-foreground italic">Not set</span>
                )}
              </p>
            )}
          </div>

          {/* Role */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70">
              Role / Title
            </label>
            {editing ? (
              <input
                type="text"
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                placeholder="e.g. Engineering Lead"
                className="w-full px-4 py-2.5 rounded-xl border bg-background text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 transition-colors"
              />
            ) : (
              <p className="text-sm text-foreground font-medium">
                {profile.jobTitle || (
                  <span className="text-muted-foreground italic">Not set</span>
                )}
              </p>
            )}
          </div>

          {/* Avatar color */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/70 flex items-center gap-1.5">
              <Palette className="w-3.5 h-3.5" />
              Avatar Color
            </label>
            <div className="grid grid-cols-6 gap-2.5 max-w-xs">
              {AVATAR_COLORS.map(({ hsl, label }) => (
                <button
                  key={label}
                  type="button"
                  aria-label={label}
                  disabled={!editing}
                  onClick={() => setColorValue(hsl)}
                  className={cn(
                    "w-8 h-8 rounded-full transition-all duration-150 ring-offset-2 ring-offset-card justify-self-center",
                    editing ? "cursor-pointer" : "cursor-default",
                    (editing ? colorValue : profile.avatarColor) === hsl
                      ? "ring-2 ring-foreground scale-110"
                      : editing
                      ? "hover:scale-105 opacity-70 hover:opacity-100"
                      : "opacity-50"
                  )}
                  style={{ background: hsl }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Save success toast */}
        {saved && (
          <div className="mx-6 mb-4 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm font-medium animate-fade-in">
            <Check className="w-4 h-4" />
            Profile saved!
          </div>
        )}
      </div>

      {/* Last updated note */}
      <div className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground/60">
        <Clock className="w-3 h-3" />
        <span>Profile is stored locally on this device</span>
      </div>
    </div>
  );
}
