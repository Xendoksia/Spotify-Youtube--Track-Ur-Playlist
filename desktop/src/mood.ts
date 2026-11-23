/** A picture's color from the backend (artwork.mood) as the CSS variables .has-mood turns into --mood. */

import type { CSSProperties } from "react";

export interface Mood {
  hue: number;
  chroma: number;
  /** The picture's second color: another hue, or its greys as a faintly tinted grey, or none */
  hue2?: number | null;
  chroma2?: number | null;
  /** Extra lightness for yellows, which look muddy at the others' lightness */
  lift?: number;
}

export function moodStyle(mood: Mood | null | undefined): CSSProperties | undefined {
  if (!mood) return undefined;
  return {
    "--mood-h": mood.hue, "--mood-c": mood.chroma, "--mood-lift": mood.lift ?? 0,
    ...(mood.hue2 != null && { "--mood-h2": mood.hue2, "--mood-c2": mood.chroma2 }),
  } as CSSProperties;
}

/** The two colors a page's curves are drawn in (api/detail.py palette): --curve-1 and --curve-2, which the
 * curves take over the page's color, so a mostly grey cover's logo still colors them. */
export function curveStyle(palette: Mood | null | undefined): CSSProperties | undefined {
  if (!palette) return undefined;
  const light = `calc(var(--mood-l) + ${palette.lift ?? 0})`;
  const second = palette.hue2 != null
    ? `oklch(calc(${light} + 0.1) ${palette.chroma2} ${palette.hue2})`
    : `oklch(calc(${light} + 0.1) ${palette.chroma} ${palette.hue + 55})`;
  return { "--curve-1": `oklch(${light} ${palette.chroma} ${palette.hue})`, "--curve-2": second } as CSSProperties;
}
