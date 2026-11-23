/** A track's place among all tracks day by day (or month by month) as a line that draws itself from left to right
 * in the two colors of its cover, the first place at the top, over a fill of its plays so far, so a track that
 * keeps its place still shows how it grows. The top ten is shaded and its best place and the day it first reached
 * the top ten are marked (api/detail.py journey). */

import { useId, useState } from "react";
import { HEIGHT, TOP, WIDTH } from "./DayCurve";

export interface Journey {
  title: string;
  points: { label: string; rank: number | null; plays: number; tooltip: string }[];
  band: string;
  plays_text: string;
  summary: string;
  best: number | null;
  best_text: string;
  top: number | null;
  top_text: string;
}

const BOTTOM = 8;
const TOP_PLACES = 10;
// The scale reaches at least this place, so a track that was always first stands high instead of filling the chart
const LEAST_LOWEST = 50;
// The plays' fill rises to this share of the chart's height
const PLAYS_REACH = 0.85;
const TICKS = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500];

export default function RankJourney({ journey, empty }: { journey: Journey; empty: string }) {
  // Without the colons React puts in, which url(#…) would not find
  const id = useId().replace(/:/g, "");
  const [hovered, setHovered] = useState<number | null>(null);
  const { points } = journey;
  const ranks = points.map((point) => point.rank).filter((rank): rank is number => rank !== null);
  if (!ranks.length) return <p className="empty chart-empty">{empty}</p>;
  const count = points.length;
  // Places on a square root scale, so a climb from 140th to 5th and one from 5th to 1st both show without the top
  // ten taking half the chart
  const lowest = Math.max(LEAST_LOWEST, Math.max(...ranks) * 1.15);
  const x = (index: number) => ((index + 0.5) / count) * WIDTH;
  const y = (rank: number) => TOP + (Math.sqrt(rank - 1) / Math.sqrt(lowest - 1)) * (HEIGHT - TOP - BOTTOM);
  const drawn = points.map((point, i) => ({ i, rank: point.rank })).filter((p): p is { i: number; rank: number } => p.rank !== null);
  const line = drawn.map((p, n) => `${n ? "L" : "M"}${x(p.i)},${y(p.rank)}`).join(" ");
  const first = drawn[0];
  const last = drawn[drawn.length - 1];
  const most = Math.max(...drawn.map((p) => points[p.i].plays), 1);
  const height = (plays: number) => HEIGHT - (plays / most) * (HEIGHT - TOP) * PLAYS_REACH;
  const plays = drawn.map((p, n) => `${n ? "L" : "M"}${x(p.i)},${height(points[p.i].plays)}`).join(" ");
  const area = `${plays} L${x(last.i)},${HEIGHT} L${x(first.i)},${HEIGHT} Z`;
  const ticks = TICKS.filter((tick) => tick <= lowest)
    .filter((tick, i, all) => i === 0 || y(tick) - y(all[i - 1]) > 18);
  const every = count > 16 ? Math.ceil(count / 12) : 1;
  const edge = (index: number) => (index < count * 0.15 ? " start" : index > count * 0.85 ? " end" : "");
  const shownHover = hovered !== null && points[hovered].rank !== null ? hovered : null;
  const marks = shownHover !== null
    ? [{ index: shownHover, text: points[shownHover].tooltip.split("\n").join("  ·  "), below: false, peak: false }]
    : [
        ...(journey.best !== null ? [{ index: journey.best, text: journey.best_text, below: false, peak: true }] : []),
        ...(journey.top !== null ? [{ index: journey.top, text: journey.top_text, below: true, peak: false }] : []),
      ];
  return (
    <div className="day-curve timeline-curve journey" onMouseLeave={() => setHovered(null)}>
      <div className="day-curve-plot">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden>
          <defs>
            <linearGradient id={`${id}line`} gradientUnits="userSpaceOnUse" x1="0" x2={WIDTH} y1="0" y2="0">
              <stop offset="0" className="journey-from" />
              <stop offset="1" className="journey-to" />
            </linearGradient>
            <linearGradient id={`${id}fill`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" className="fill-top" />
              <stop offset="1" className="fill-bottom" />
            </linearGradient>
            <clipPath id={`${id}reveal`}>
              <rect width={WIDTH} height={HEIGHT + 4} y="-2" className="timeline-reveal" />
            </clipPath>
          </defs>
          <rect x="0" width={WIDTH} y={y(1) - 4} height={y(TOP_PLACES) - y(1) + 4} rx="6" className="journey-band" />
          {ticks.filter((tick) => tick > 1).map((tick) => (
            <line key={tick} x1="0" x2={WIDTH} y1={y(tick)} y2={y(tick)} className="timeline-grid" />
          ))}
          <g clipPath={`url(#${id}reveal)`}>
            <path d={area} fill={`url(#${id}fill)`} className="journey-area" />
            <path d={line} className="day-curve-line" style={{ stroke: `url(#${id}line)` }} />
          </g>
          {shownHover !== null && (
            <line x1={x(shownHover)} x2={x(shownHover)} y1={y(points[shownHover].rank!)} y2={HEIGHT}
                  className="day-curve-guide" />
          )}
        </svg>
        <span className="journey-plays timeline-late">{journey.plays_text}</span>
        <span className="journey-band-label timeline-late" style={{ top: `${((y(TOP_PLACES) - 2) / HEIGHT) * 100}%` }}>
          {journey.band}
        </span>
        <div className="journey-ticks">
          {ticks.map((tick) => (
            <span key={tick} style={{ top: `${(y(tick) / HEIGHT) * 100}%` }}>{tick}.</span>
          ))}
        </div>
        {marks.map((mark) => (
          <span key={`${mark.index}${mark.below}`}
                className={`day-curve-dot${shownHover === null ? " timeline-late" : ""}${mark.peak ? " peak" : ""}${mark.below ? " below" : ""}${edge(mark.index)}`}
                style={{ left: `${(x(mark.index) / WIDTH) * 100}%`, top: `${(y(points[mark.index].rank!) / HEIGHT) * 100}%` }}>
            <span className="day-curve-label">{mark.text}</span>
          </span>
        ))}
        <div className="day-curve-hours" style={{ gridTemplateColumns: `repeat(${count}, 1fr)` }}>
          {points.map((point, index) => (
            <span key={index} onMouseEnter={() => setHovered(index)} aria-label={point.tooltip} />
          ))}
        </div>
      </div>
      <div className="timeline-axis" style={{ gridTemplateColumns: `repeat(${count}, 1fr)` }}>
        {points.map((point, index) => <span key={index}>{index % every === 0 ? point.label : ""}</span>)}
      </div>
    </div>
  );
}
