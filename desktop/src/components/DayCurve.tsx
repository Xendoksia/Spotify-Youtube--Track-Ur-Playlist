/** The plays of the 24 hours as one soft curve in the page's color, over a faint band of night, dawn, day and
 * dusk, with the most played hour marked and each hour's count on hover (api/detail.py day_curve). */

import { ReactNode, useState } from "react";
import type { Bucket } from "./ColumnChart";

const WIDTH = 720;
const HEIGHT = 200;
const TOP = 34;

type Point = [number, number];

/** A smooth line through the points (Catmull-Rom as cubic Béziers), kept between the top and the baseline */
function smooth(points: Point[]): string {
  const keep = (y: number) => Math.min(HEIGHT, Math.max(TOP / 2, y));
  let path = `M${points[1][0]},${points[1][1]}`;
  for (let i = 1; i < points.length - 2; i++) {
    const [p0, p1, p2, p3] = [points[i - 1], points[i], points[i + 1], points[i + 2]];
    const c1: Point = [p1[0] + (p2[0] - p0[0]) / 6, keep(p1[1] + (p2[1] - p0[1]) / 6)];
    const c2: Point = [p2[0] - (p3[0] - p1[0]) / 6, keep(p2[1] - (p3[1] - p1[1]) / 6)];
    path += ` C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${p2[0]},${p2[1]}`;
  }
  return path;
}

function Moon() {
  return <svg viewBox="0 0 16 16"><path d="M10.5 2.5a5.5 5.5 0 1 0 3 9.8A6 6 0 0 1 10.5 2.5z" /></svg>;
}

function Sun({ rising }: { rising?: boolean }) {
  // A whole sun at noon, half of one on the horizon at dawn and dusk
  if (rising) {
    return (
      <svg viewBox="0 0 16 16">
        <path d="M3.5 11a4.5 4.5 0 0 1 9 0z" />
        <path d="M1 13h14M8 2.5v2M3 5l1.4 1.4M13 5l-1.4 1.4" className="ray" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 16 16">
      <circle cx="8" cy="8" r="3.2" />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M13 3l-1.4 1.4M4.4 11.6L3 13" className="ray" />
    </svg>
  );
}

const MARKS: { hour: number; icon: ReactNode }[] = [
  { hour: 0, icon: <Moon /> }, { hour: 6, icon: <Sun rising /> }, { hour: 12, icon: <Sun /> },
  { hour: 18, icon: <Sun rising /> }, { hour: 24, icon: <Moon /> },
];

export default function DayCurve({ buckets, peak, peakText, empty }: {
  buckets: Bucket[]; peak: number | null; peakText: string; empty: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const most = Math.max(...buckets.map((bucket) => bucket.value), 0);
  if (!most) return <p className="empty chart-empty">{empty}</p>;
  const x = (hour: number) => ((hour + 0.5) / 24) * WIDTH;
  const y = (value: number) => HEIGHT - (value / most) * (HEIGHT - TOP);
  const value = (hour: number) => buckets[(hour + 24) % 24].value;
  // The day goes round: the hours before midnight lead into the first ones, so the curve does not drop at the ends
  const points: Point[] = [];
  for (let hour = -2; hour <= 25; hour++) points.push([x(hour), y(value(hour))]);
  const line = smooth(points);
  const area = `${line} L${x(24)},${HEIGHT} L${x(-1)},${HEIGHT} Z`;
  const shown = hovered ?? peak;
  return (
    <div className="day-curve" onMouseLeave={() => setHovered(null)}>
      <div className="day-curve-plot">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden>
          <defs>
            <linearGradient id="day-band" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0" className="band-night" />
              <stop offset="0.25" className="band-dawn" />
              <stop offset="0.5" className="band-noon" />
              <stop offset="0.75" className="band-dusk" />
              <stop offset="1" className="band-night" />
            </linearGradient>
            <linearGradient id="day-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" className="fill-top" />
              <stop offset="1" className="fill-bottom" />
            </linearGradient>
          </defs>
          <rect width={WIDTH} height={HEIGHT} fill="url(#day-band)" rx="10" />
          <path d={area} fill="url(#day-fill)" />
          <path d={line} className="day-curve-line" />
          {shown !== null && (
            <line x1={x(shown)} x2={x(shown)} y1={y(value(shown))} y2={HEIGHT} className="day-curve-guide" />
          )}
        </svg>
        {shown !== null && (
          // Near an edge the label leans inward, so it stays inside the card
          <span className={`day-curve-dot${hovered === null ? " peak" : ""}${shown < 4 ? " start" : shown > 19 ? " end" : ""}`}
                style={{ left: `${(x(shown) / WIDTH) * 100}%`, top: `${(y(value(shown)) / HEIGHT) * 100}%` }}>
            <span className="day-curve-label">
              {hovered === null ? peakText : buckets[hovered].tooltip.split("\n").join("  ·  ")}
            </span>
          </span>
        )}
        <div className="day-curve-hours">
          {buckets.map((bucket, hour) => (
            <span key={hour} onMouseEnter={() => setHovered(hour)} aria-label={bucket.tooltip} />
          ))}
        </div>
      </div>
      <div className="day-curve-axis">
        {MARKS.map((mark) => (
          <span key={mark.hour} className="day-curve-mark" style={{ left: `${(mark.hour / 24) * 100}%` }}>
            {mark.icon}
            {String(mark.hour).padStart(2, "0")}
          </span>
        ))}
      </div>
    </div>
  );
}
