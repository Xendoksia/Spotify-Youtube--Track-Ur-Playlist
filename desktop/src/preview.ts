/** Deezer's 30 second previews of suggested songs (api/recommend.py), one at a time, played in the window. */

import { useSyncExternalStore } from "react";
import { get } from "./api";

export type PreviewState = "idle" | "loading" | "playing" | "none";

interface Playing {
  /** artist|title of the song playing or being looked up */
  key: string;
  state: PreviewState;
  /** 0 to 1 through the preview */
  progress: number;
}

const audio = new Audio();
audio.volume = 0.56;
let current: Playing = { key: "", state: "idle", progress: 0 };
// Songs without a preview, so their buttons stay off
const missing = new Set<string>();
const listeners = new Set<() => void>();
// Preview addresses looked up ahead or before, with when, as they are signed for a while
const KEEP_MS = 25 * 60 * 1000;
const urls = new Map<string, { url: string | null; at: number }>();
// Loaded ahead, so they start at once (kept so the browser keeps their data)
const loaded = new Map<string, HTMLAudioElement>();

async function urlOf(artist: string, title: string): Promise<string | null> {
  const key = `${artist}|${title}`;
  const kept = urls.get(key);
  if (kept && Date.now() - kept.at < KEEP_MS) return kept.url;
  const { url } = await get<{ url: string | null }>("/api/recommend/preview", { artist, title });
  urls.set(key, { url, at: Date.now() });
  return url;
}

/** Look up and load a preview ahead, so it plays at once when asked (the summary's songs) */
export async function preloadPreview(artist: string, title: string) {
  try {
    const url = await urlOf(artist, title);
    if (!url || loaded.has(url)) return;
    const ahead = new Audio();
    ahead.preload = "auto";
    ahead.src = url;
    loaded.set(url, ahead);
  } catch {
    // Asked again when played
  }
}

/** Hold the preview playing, or go on with it (the summary paused) */
export function holdPreview(hold: boolean) {
  if (current.state !== "playing") return;
  if (hold) audio.pause();
  else audio.play().catch(() => undefined);
}

function set(next: Playing) {
  current = next;
  listeners.forEach((listener) => listener());
}

audio.addEventListener("timeupdate", () => {
  if (current.state === "playing" && audio.duration) set({ ...current, progress: audio.currentTime / audio.duration });
});
audio.addEventListener("ended", () => set({ key: "", state: "idle", progress: 0 }));

export function stopPreview() {
  audio.pause();
  if (current.key) set({ key: "", state: "idle", progress: 0 });
}

async function toggle(artist: string, title: string) {
  const key = `${artist}|${title}`;
  if (current.key === key) {
    stopPreview();
    return;
  }
  audio.pause();
  set({ key, state: "loading", progress: 0 });
  try {
    const url = await urlOf(artist, title);
    // Another song was clicked meanwhile
    if (current.key !== key) return;
    if (!url) {
      missing.add(key);
      set({ key: "", state: "idle", progress: 0 });
      return;
    }
    audio.src = url;
    await audio.play();
    if (current.key === key) set({ key, state: "playing", progress: 0 });
  } catch {
    if (current.key === key) set({ key: "", state: "idle", progress: 0 });
  }
}

/** Play a song's preview unless it is the one playing already (as a slide of the summary does) */
export function playPreview(artist: string, title: string) {
  if (current.key !== `${artist}|${title}`) toggle(artist, title);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The song's preview state and a click handler that plays or stops it */
export function usePreview(artist: string, title: string) {
  const key = `${artist}|${title}`;
  const playing = useSyncExternalStore(subscribe, () => current);
  const state: PreviewState = missing.has(key) ? "none" : playing.key === key ? playing.state : "idle";
  return { state, progress: playing.key === key ? playing.progress : 0, toggle: () => toggle(artist, title) };
}
