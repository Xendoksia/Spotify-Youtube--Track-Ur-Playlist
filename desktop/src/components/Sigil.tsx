/** A ring drawn in the manner of a genre family round its middle, as the phone's GenreSigil
 * (mobile/lib/screens/listening/wrapped_visuals.dart): sharp spikes for metal, thick bars for rock, stepped bars for
 * electronic music, bouncing dots for pop, soft waves for jazz and calm music, an eight pointed star for Turkish
 * music. It is drawn once; turning and beating are CSS transforms on it, so nothing is painted again. */

import type { ReactNode } from "react";

/** A number from 0 to 1 that looks random but is the same for the same i and seed, as on the phone */
function noise(i: number, seed: number): number {
  const v = Math.sin(i * 12.9898 + seed * 78.233) * 43758.5453;
  return v - Math.floor(v);
}

const SIZE = 200;
const C = SIZE / 2;
const INNER = SIZE * 0.37;
const REACH = SIZE * 0.12;

function at(angle: number, radius: number): [number, number] {
  return [C + Math.cos(angle) * radius, C + Math.sin(angle) * radius];
}

function shapes(family: string): ReactNode {
  const seed = family.length;
  const turn = (i: number, count: number) => (i / count) * 2 * Math.PI;
  const line = (key: string | number, a: number, from: number, to: number, width: number, cap = "round") => {
    const [x1, y1] = at(a, from);
    const [x2, y2] = at(a, to);
    return <line key={key} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#fff" strokeWidth={width} strokeLinecap={cap as "round"} />;
  };
  switch (family) {
    case "metal": {
      const count = 44;
      const d = Array.from({ length: count }, (_, i) => {
        const a = turn(i, count);
        const half = (Math.PI / count) * 0.8;
        const [x1, y1] = at(a - half, INNER);
        const [x2, y2] = at(a, INNER + REACH * (0.35 + 0.65 * noise(i, seed)));
        const [x3, y3] = at(a + half, INNER);
        return `M${x1} ${y1}L${x2} ${y2}L${x3} ${y3}Z`;
      }).join("");
      return <path d={d} fill="#fff" />;
    }
    case "rock":
      return Array.from({ length: 26 }, (_, i) =>
        line(i, turn(i, 26), INNER + 3, INNER + 3 + REACH * (0.3 + 0.7 * noise(i, seed)), SIZE * 0.03));
    case "electronic":
      return [
        ...Array.from({ length: 36 }, (_, i) =>
          line(i, turn(i, 36), INNER + 4, INNER + 4 + (REACH * (1 + Math.floor(noise(i, seed) * 4))) / 4, SIZE * 0.022, "butt")),
        ...Array.from({ length: 72 }, (_, i) => {
          const [x, y] = at(turn(i, 72), INNER - 1);
          return <circle key={`dot${i}`} cx={x} cy={y} r={1} fill="#fff" />;
        }),
      ];
    case "hiphop":
      return [
        ...Array.from({ length: 14 }, (_, i) =>
          line(i, turn(i, 14), INNER + 6, INNER + 6 + REACH * (0.2 + 0.5 * noise(i, seed)), SIZE * 0.06)),
        <circle key="in" cx={C} cy={C} r={INNER + 1} fill="none" stroke="#fff" strokeWidth={2} />,
        <circle key="out" cx={C} cy={C} r={INNER + REACH + 8} fill="none" stroke="rgb(255 255 255 / 0.5)" strokeWidth={2} />,
      ];
    case "pop":
      return Array.from({ length: 20 }, (_, i) => {
        const [x, y] = at(turn(i, 20), INNER + REACH * 0.55 + 6 * Math.sin(i * 1.7));
        return <circle key={i} cx={x} cy={y} r={SIZE * (0.015 + 0.03 * noise(i, seed))} fill="#fff" />;
      });
    case "jazz":
    case "calm":
    case "latin": {
      const waves = family === "calm" ? 6 : family === "latin" ? 14 : 9;
      return [[0, 1], [1, 0.45]].map(([k, alpha]) => {
        const d = Array.from({ length: 241 }, (_, s) => {
          const a = (s / 240) * 2 * Math.PI;
          const [x, y] = at(a, INNER + REACH * (0.45 + 0.35 * Math.sin(a * waves + k * 1.2)) + k * 6);
          return `${s ? "L" : "M"}${x} ${y}`;
        }).join("");
        return <path key={k} d={d} fill="none" stroke={`rgb(255 255 255 / ${alpha})`} strokeWidth={2.5} />;
      });
    }
    case "turkish":
      return [
        ...[0, Math.PI / 4].map((start, k) => {
          const points = Array.from({ length: 4 }, (_, i) => at(start + (i * Math.PI) / 2, INNER + REACH * 0.95).join(","));
          return <polygon key={k} points={points.join(" ")} fill="none" stroke="#fff" strokeWidth={2.5} />;
        }),
        ...Array.from({ length: 32 }, (_, i) => {
          const [x, y] = at(turn(i, 32), INNER + REACH + 6);
          return <circle key={`dot${i}`} cx={x} cy={y} r={1.6} fill="#fff" />;
        }),
      ];
    case "folk":
      return Array.from({ length: 12 }, (_, i) => {
        const a = turn(i, 12);
        const [x, y] = at(a, INNER + REACH * 0.55);
        return <ellipse key={i} cx={x} cy={y} rx={REACH * 0.475} ry={REACH * 0.19} fill="#fff"
                        transform={`rotate(${(a * 180) / Math.PI} ${x} ${y})`} />;
      });
    default:
      return Array.from({ length: 5 }, (_, k) => (
        <circle key={k} cx={C} cy={C} r={INNER + 4 + (k * REACH) / 5} fill="none"
                stroke={`rgb(255 255 255 / ${1 - k * 0.17})`} strokeWidth={1.5} />
      ));
  }
}

/** How fast a family's sigil beats, faster for heavier music */
const BEATS: Record<string, number> = { metal: 520, electronic: 700, hiphop: 700, rock: 900, pop: 900, latin: 900 };

export default function Sigil({ family, size, still = false, children }: {
  family: string; size: number; still?: boolean; children?: ReactNode;
}) {
  return (
    <span className={still ? "sigil still" : "sigil"} style={{ width: size, height: size }}>
      <span className="sigil-beat" style={{ animationDuration: `${BEATS[family] ?? 1800}ms` }}>
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="sigil-ring">{shapes(family)}</svg>
      </span>
      {children && <span className="sigil-middle">{children}</span>}
    </span>
  );
}
