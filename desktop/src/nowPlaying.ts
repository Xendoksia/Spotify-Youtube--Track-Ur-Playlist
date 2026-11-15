/** What Spotify plays now (api/listening.py now_playing), asked for often while the window is seen and shared by
 * the mini player and the Recently played tab. */

import { createContext, useContext, useEffect, useState } from "react";
import { get } from "./api";

export interface NowPlaying {
  available: boolean;
  enabled: boolean;
  state: "off" | "idle" | "playing" | "paused";
  error: string | null;
  play: {
    key: string;
    name: string;
    artist: string;
    album: string;
    recorded: boolean;
    position: number | null;
    duration: number | null;
    listened: string;
    image: string;
  } | null;
}

// Often enough for the clock to tick each second; paused, idle or hidden in the tray only a change has to show
const PLAYING_MS = 500;
const IDLE_MS = 1000;
const HIDDEN_MS = 5000;

export function useNowPlayingPoll(): NowPlaying | null {
  const [now, setNow] = useState<NowPlaying | null>(null);
  useEffect(() => {
    let timer = 0;
    let stopped = false;
    const ask = async () => {
      let state: NowPlaying["state"] = "off";
      try {
        const result = await get<NowPlaying>("/api/now");
        if (stopped) return;
        setNow(result);
        state = result.state;
      } catch {
        // The backend is starting or stopping: asked again shortly
      }
      if (!stopped) timer = window.setTimeout(ask, document.hidden ? HIDDEN_MS : state === "playing" ? PLAYING_MS : IDLE_MS);
    };
    ask();
    // Shown from the tray: up to date at once, not at the next ask
    const onVisible = () => {
      if (!document.hidden) {
        window.clearTimeout(timer);
        ask();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return now;
}

export const NowPlayingContext = createContext<NowPlaying | null>(null);

export const useNowPlaying = () => useContext(NowPlayingContext);

export function clock(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
