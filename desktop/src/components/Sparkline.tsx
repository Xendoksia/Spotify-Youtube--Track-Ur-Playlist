import { useState } from "react";

export interface TrendPoint {
  value: number;
  tooltip: string;
}

const HEIGHT = 34;
// Room above the highest point and below the line's lowest, so the 2px line and the dot are not cut off
const PAD = 3;

/** A tile's value over the days (or months) of the period as a thin line over a soft area; hovering shows
 * each point's value. Nothing is drawn for fewer than two points. */
export default function Sparkline({ points }: { points: TrendPoint[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (points.length < 2) return null;
  const most = Math.max(...points.map((point) => point.value), 1);
  const x = (index: number) => (index * 100) / (points.length - 1);
  const y = (value: number) => PAD + (HEIGHT - 2 * PAD) * (1 - value / most);
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(index)},${y(point.value)}`).join("");
  const area = `${line}L100,${HEIGHT}L0,${HEIGHT}Z`;
  const shown = hovered ?? points.length - 1;
  const left = x(shown);

  return (
    <div
      className="sparkline"
      onMouseMove={(event) => {
        const box = event.currentTarget.getBoundingClientRect();
        const index = Math.round(((event.clientX - box.left) / box.width) * (points.length - 1));
        setHovered(Math.max(0, Math.min(points.length - 1, index)));
      }}
      onMouseLeave={() => setHovered(null)}
    >
      <svg viewBox={`0 0 100 ${HEIGHT}`} preserveAspectRatio="none" aria-hidden>
        <path key={`a${line}`} className="sparkline-area" d={area} />
        <path key={line} className="sparkline-line" d={line} pathLength={1} />
        {hovered !== null && <line className="sparkline-rule" x1={left} x2={left} y1={0} y2={HEIGHT} />}
      </svg>
      {/* The dot is HTML so the stretched drawing does not stretch it into an oval */}
      <span className="sparkline-dot" style={{ left: `${left}%`, top: y(points[shown].value) }} />
      {hovered !== null && (
        <span className={`sparkline-tip${left > 60 ? " end" : ""}`} style={{ left: `${left}%` }}>
          {points[hovered].tooltip}
        </span>
      )}
    </div>
  );
}
