import { useState } from "react";
import { useTexts } from "../i18n";
import { Bucket } from "./ColumnChart";

const SIZE = 260;
const CENTER = SIZE / 2;
const INNER = 46;
const OUTER = 108;
// The space left between two hours' slices, in radians
const GAP = 0.025;

/** A ring slice from angle a0 to a1 (radians, clockwise from the top) between two radii */
function slice(r0: number, r1: number, a0: number, a1: number): string {
  const point = (r: number, a: number) => `${CENTER + r * Math.sin(a)},${CENTER - r * Math.cos(a)}`;
  return `M${point(r1, a0)} A${r1},${r1} 0 0 1 ${point(r1, a1)} L${point(r0, a1)} A${r0},${r0} 0 0 0 ${point(r0, a0)} Z`;
}

/** The plays of the 24 hours as slices round a clock face, midnight at the top and noon at the bottom, each reaching
 * out as far as its count, in the page's color. The middle names the busiest hour, or the hour under the pointer. */
export default function HourClock({ buckets, empty }: { buckets: Bucket[]; empty: string }) {
  const { t } = useTexts();
  const [hovered, setHovered] = useState<number | null>(null);
  const most = Math.max(...buckets.map((bucket) => bucket.value), 0);
  if (!most) return <p className="empty chart-empty">{empty}</p>;
  const peak = buckets.findIndex((bucket) => bucket.value === most);
  const shown = hovered ?? peak;
  // The tooltip's two lines: the hour ("21:00 – 22:00") and its plays
  const [range, plays] = buckets[shown].tooltip.split("\n");
  const step = (2 * Math.PI) / buckets.length;
  return (
    <div className="hour-clock" onMouseLeave={() => setHovered(null)}>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${t("stats.clock.peak")}: ${buckets[peak].tooltip}`}>
        <circle className="hour-clock-ring" cx={CENTER} cy={CENTER} r={OUTER} />
        <circle className="hour-clock-ring half" cx={CENTER} cy={CENTER} r={(INNER + OUTER) / 2} />
        <g className="hour-clock-slices">
          {buckets.map((bucket, hour) => {
            const reach = bucket.value ? INNER + 3 + ((OUTER - INNER - 3) * bucket.value) / most : INNER + 1.5;
            return (
              <path
                key={hour}
                d={slice(INNER, reach, hour * step + GAP, (hour + 1) * step - GAP)}
                className={`hour-clock-slice${hour === shown ? " shown" : ""}`}
                style={{ opacity: hour === shown ? 1 : 0.35 + (0.5 * bucket.value) / most }}
              />
            );
          })}
        </g>
        {/* Wider wedges over the slices, so a short hour is as easy to point at as a long one */}
        {buckets.map((_, hour) => (
          <path key={hour} d={slice(INNER, OUTER + 8, hour * step, (hour + 1) * step)} className="hour-clock-hit"
                onMouseEnter={() => setHovered(hour)} />
        ))}
        {[0, 6, 12, 18].map((hour) => {
          const angle = hour * step;
          return (
            <text key={hour} className="hour-clock-mark" x={CENTER + (OUTER + 14) * Math.sin(angle)}
                  y={CENTER - (OUTER + 14) * Math.cos(angle)}>
              {String(hour).padStart(2, "0")}
            </text>
          );
        })}
        <text className="hour-clock-hour" x={CENTER} y={CENTER - 6}>{range.split(" ")[0]}</text>
        <text className="hour-clock-caption" x={CENTER} y={CENTER + 17}>
          {hovered === null ? t("stats.clock.peak") : plays}
        </text>
      </svg>
    </div>
  );
}
