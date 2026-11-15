/** A picture's color from the backend (artwork.mood) as the CSS variables .has-mood turns into --mood. */

import type { CSSProperties } from "react";

export interface Mood {
  hue: number;
  chroma: number;
}

export function moodStyle(mood: Mood | null | undefined): CSSProperties | undefined {
  return mood ? { "--mood-h": mood.hue, "--mood-c": mood.chroma } as CSSProperties : undefined;
}
