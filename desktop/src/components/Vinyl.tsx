/** An album as a record: its tracks in album order as slices going round clockwise, each reaching out as far as it
 * was played and an unheard one left as a thin groove, in the two colors of the cover, with how many tracks were
 * heard on the label. The slices open out one after another; a slice tells its track on hover and opens it on a
 * click (api/detail.py vinyl). */

import { useEffect, useId, useState } from "react";
import type { BarRow } from "./BarList";

export interface VinylData {
  title: string;
  summary: string;
  center: string;
  caption: string;
}

const SIZE = 320;
const CENTER = SIZE / 2;
const LABEL = 46;
const INNER = 60;
const OUTER = 138;
const GAP = 0.035;
const OPENING_MS = 1400;

/** A ring slice from angle a0 to a1 (radians, clockwise from the top) between two radii */
function slice(a0: number, a1: number, inner: number, outer: number): string {
  const at = (angle: number, radius: number) =>
    `${CENTER + radius * Math.sin(angle)},${CENTER - radius * Math.cos(angle)}`;
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M${at(a0, outer)} A${outer},${outer} 0 ${large} 1 ${at(a1, outer)} L${at(a1, inner)} `
    + `A${inner},${inner} 0 ${large} 0 ${at(a0, inner)} Z`;
}

export default function Vinyl({ rows, data, onOpen }: {
  rows: BarRow[]; data: VinylData; onOpen: (row: BarRow) => void;
}) {
  // Without the colons React puts in, which url(#…) would not find
  const id = useId().replace(/:/g, "");
  const [hovered, setHovered] = useState<number | null>(null);
  const [opened, setOpened] = useState(0);

  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setOpened(1);
      return;
    }
    const start = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const done = Math.min(1, (now - start) / OPENING_MS);
      setOpened(1 - Math.pow(1 - done, 3));
      if (done < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [rows.length]);

  const count = rows.length;
  if (!count) return null;
  const most = Math.max(...rows.map((row) => row.value), 1);
  const best = rows.findIndex((row) => row.value === most);
  const step = (2 * Math.PI) / count;
  const shown = hovered !== null ? rows[hovered] : null;
  return (
    <div className="day-curve vinyl">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="vinyl-record" onMouseLeave={() => setHovered(null)}>
        <defs>
          <radialGradient id={`${id}fill`} cx={CENTER} cy={CENTER} r={OUTER} gradientUnits="userSpaceOnUse">
            <stop offset={INNER / OUTER} className="vinyl-from" />
            <stop offset="1" className="vinyl-to" />
          </radialGradient>
        </defs>
        <circle cx={CENTER} cy={CENTER} r={OUTER + 4} className="vinyl-disc" />
        {Array.from({ length: Math.floor((OUTER - INNER - 8) / 10) }, (_, i) => (
          <circle key={i} cx={CENTER} cy={CENTER} r={INNER + 8 + i * 10} className="vinyl-groove" />
        ))}
        {rows.map((row, i) => {
          const a0 = i * step + GAP;
          const a1 = (i + 1) * step - GAP;
          const reach = row.value ? INNER + 16 + (OUTER - INNER - 16) * Math.sqrt(row.value / most) : INNER + 5;
          // One after another round the record
          const own = Math.max(0, Math.min(1, opened * 1.6 - (i / count) * 0.6));
          const middle = (a0 + a1) / 2;
          return (
            <g key={row.key}>
              <path d={slice(a0, a1, INNER, INNER + (reach - INNER) * own)}
                    className={`vinyl-slice${row.value ? "" : " unheard"}${i === best ? " best" : ""}${i === hovered ? " hovered" : ""}`}
                    fill={row.value ? `url(#${id}fill)` : undefined} />
              <text x={CENTER + (OUTER + 16) * Math.sin(middle)} y={CENTER - (OUTER + 16) * Math.cos(middle) + 4}
                    className="vinyl-number">{i + 1}</text>
              <path d={slice(a0, a1, INNER, OUTER + 8)} className={`vinyl-hit${row.column ? " clickable" : ""}`}
                    onMouseEnter={() => setHovered(i)} onClick={() => row.column && onOpen(row)} />
            </g>
          );
        })}
        <circle cx={CENTER} cy={CENTER} r={LABEL + 10} className="vinyl-rim" />
        <circle cx={CENTER} cy={CENTER} r={LABEL} className="vinyl-label" />
        <g className="timeline-late">
          <text x={CENTER} y={CENTER - 4} className="vinyl-count">{data.center}</text>
          <text x={CENTER} y={CENTER + 15} className="vinyl-caption">{data.caption}</text>
        </g>
      </svg>
      <p className="vinyl-line">
        {shown ? <><strong>{rows.indexOf(shown) + 1}. {shown.title}</strong>  ·  {shown.detail}</> : data.summary}
      </p>
    </div>
  );
}
