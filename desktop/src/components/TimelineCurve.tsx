/** An artist's plays over time as a curve that draws itself from left to right in the two colors of their
 * picture, fading in from the left, with the most played day or month marked, and the last days against the days before
 * them as an arrow over it (api/detail.py with_peak, trend). */

import { useId, useState } from "react";
import type { Bucket } from "./ColumnChart";
import { HEIGHT, Point, smooth, TOP, WIDTH } from "./DayCurve";

export interface Trend {
  direction: "up" | "down" | "same" | "";
  change: string;
  against: string;
  recent: string;
}

function Arrow({ down }: { down: boolean }) {
  return (
    <svg viewBox="0 0 14 14" className="trend-arrow" aria-hidden>
      <path d={down ? "M7 12.5 2 7h3.2V1.5h3.6V7H12z" : "M7 1.5 12 7H8.8v5.5H5.2V7H2z"} />
    </svg>
  );
}

export default function TimelineCurve({ buckets, peak, peakText, trend, empty }: {
  buckets: Bucket[]; peak: number | null; peakText: string; trend: Trend | null; empty: string;
}) {
  // Without the colons React puts in, which url(#…) would not find
  const id = useId().replace(/:/g, "");
  const [hovered, setHovered] = useState<number | null>(null);
  const most = Math.max(...buckets.map((bucket) => bucket.value), 0);
  if (!most) return <p className="empty chart-empty">{empty}</p>;
  const count = buckets.length;
  const x = (index: number) => ((index + 0.5) / count) * WIDTH;
  const y = (value: number) => HEIGHT - (value / most) * (HEIGHT - TOP);
  const first = y(buckets[0].value);
  const last = y(buckets[count - 1].value);
  // The line runs on flat to both edges, so it does not end in the air half a column in
  const points: Point[] = [[0, first], [0, first], ...buckets.map((bucket, i): Point => [x(i), y(bucket.value)]),
                           [WIDTH, last], [WIDTH, last]];
  const line = smooth(points);
  const area = `${line} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`;
  const shown = hovered ?? peak;
  const every = count > 16 ? Math.ceil(count / 12) : 1;
  const edge = (index: number) => (index < count * 0.15 ? " start" : index > count * 0.85 ? " end" : "");
  return (
    <div className="day-curve timeline-curve" onMouseLeave={() => setHovered(null)}>
      {trend && (
        <div className={`trend ${trend.direction}`}>
          {trend.direction && trend.direction !== "same" && (
            <span className="trend-pill"><Arrow down={trend.direction === "down"} />{trend.change}</span>
          )}
          <span className="muted">{[trend.recent, trend.against].filter(Boolean).join("  ·  ")}</span>
        </div>
      )}
      <div className="day-curve-plot">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden>
          <defs>
            <linearGradient id={`${id}line`} gradientUnits="userSpaceOnUse" x1="0" x2={WIDTH} y1="0" y2="0">
              <stop offset="0" className="line-faint" />
              <stop offset="0.7" className="line-full" />
            </linearGradient>
            <linearGradient id={`${id}fill`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" className="fill-top" />
              <stop offset="1" className="fill-bottom" />
            </linearGradient>
            <clipPath id={`${id}reveal`}>
              <rect width={WIDTH} height={HEIGHT + 4} y="-2" className="timeline-reveal" />
            </clipPath>
          </defs>
          {[0.25, 0.5, 0.75].map((part) => (
            <line key={part} x1="0" x2={WIDTH} y1={TOP + (HEIGHT - TOP) * part} y2={TOP + (HEIGHT - TOP) * part}
                  className="timeline-grid" />
          ))}
          <g clipPath={`url(#${id}reveal)`}>
            <path d={area} fill={`url(#${id}fill)`} />
            <path d={line} className="day-curve-line" style={{ stroke: `url(#${id}line)` }} />
          </g>
          {shown !== null && (
            <line x1={x(shown)} x2={x(shown)} y1={y(buckets[shown].value)} y2={HEIGHT}
                  className="day-curve-guide timeline-late" />
          )}
        </svg>
        {shown !== null && (
          <span className={`day-curve-dot timeline-late${hovered === null ? " peak" : ""}${edge(shown)}`}
                style={{ left: `${(x(shown) / WIDTH) * 100}%`, top: `${(y(buckets[shown].value) / HEIGHT) * 100}%` }}>
            <span className="day-curve-label">
              {hovered === null ? peakText : buckets[hovered].tooltip.split("\n").join("  ·  ")}
            </span>
          </span>
        )}
        <div className="day-curve-hours" style={{ gridTemplateColumns: `repeat(${count}, 1fr)` }}>
          {buckets.map((bucket, index) => (
            <span key={index} onMouseEnter={() => setHovered(index)} aria-label={bucket.tooltip} />
          ))}
        </div>
      </div>
      <div className="timeline-axis" style={{ gridTemplateColumns: `repeat(${count}, 1fr)` }}>
        {buckets.map((bucket, index) => <span key={index}>{index % every === 0 ? bucket.label : ""}</span>)}
      </div>
    </div>
  );
}
