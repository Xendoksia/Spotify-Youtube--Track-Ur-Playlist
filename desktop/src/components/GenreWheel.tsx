import { Series } from "./StackedColumns";

export interface RingSlice {
  series: Series;
  text: string;
  share: number;
  percent: string;
}

export interface FamilyWeb {
  axes: { name: string; now: number; before: number | null; tooltip: string }[];
  legend: { current: string; previous: string } | null;
}

/** A ring slice from angle a0 to a1 (radians, clockwise from the top) between two radii, round a center */
function slice(center: number, r0: number, r1: number, a0: number, a1: number): string {
  const point = (r: number, a: number) => `${center + r * Math.sin(a)},${center - r * Math.cos(a)}`;
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M${point(r1, a0)} A${r1},${r1} 0 ${large} 1 ${point(r1, a1)} L${point(r0, a1)} `
    + `A${r0},${r0} 0 ${large} 0 ${point(r0, a0)} Z`;
}

/** The period's biggest genres and the rest as a ring in the genres' colors, the biggest named in the middle, with
 * the slices' names and shares beside it. */
export function GenreRing({ slices }: { slices: RingSlice[] }) {
  const size = 180;
  const center = size / 2;
  let angle = 0;
  const gap = slices.length > 1 ? 0.03 : 0;
  return (
    <div className="genre-ring">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={slices.map((s) => `${s.text} ${s.percent}`).join(", ")}>
        {slices.map((item) => {
          const start = angle;
          angle += item.share * 2 * Math.PI;
          // A single genre's whole circle stops just short, as an arc cannot close on itself
          const end = Math.min(angle, start + 2 * Math.PI - 0.0001);
          return (
            <path key={item.series} className={`ring-slice ring-${item.series}`}
                  d={slice(center, 56, 86, start + gap / 2, Math.max(start + gap / 2, end - gap / 2))}>
              <title>{`${item.text}\n${item.percent}`}</title>
            </path>
          );
        })}
        <text className="ring-name" x={center} y={center - 6}>{slices[0].text}</text>
        <text className="ring-share" x={center} y={center + 13}>{slices[0].percent}</text>
      </svg>
      <ul className="ring-legend">
        {slices.map((item) => (
          <li key={item.series}>
            <span className={`swatch series-${item.series}`} />
            <span className="ring-legend-name">{item.text}</span>
            <span className="ring-legend-share">{item.percent}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The genre families' weight as a web, the period's shape in the page's color over the previous period's dashed
 * outline. The distance from the middle grows with the square root of the share, so a family of a few percent
 * still shows beside one of half the plays. */
export function FamilyWeb({ data }: { data: FamilyWeb }) {
  const size = 220;
  const center = size / 2;
  const radius = 72;
  const count = data.axes.length;
  const most = Math.max(...data.axes.map((axis) => Math.max(axis.now, axis.before ?? 0)), 0.01);
  const point = (index: number, share: number) => {
    const angle = (index / count) * 2 * Math.PI;
    const r = radius * Math.sqrt(share / most);
    return [center + r * Math.sin(angle), center - r * Math.cos(angle)] as const;
  };
  const outline = (shares: number[]) => shares.map((share, index) => point(index, share).join(",")).join(" ");
  const ring = (share: number) => data.axes.map((_, index) => point(index, share * most).join(",")).join(" ");
  return (
    <div className="family-web">
      {data.legend && (
        <div className="legend">
          <span className="legend-item"><span className="swatch web-now" />{data.legend.current}</span>
          <span className="legend-item"><span className="swatch web-before" />{data.legend.previous}</span>
        </div>
      )}
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={data.axes.map((axis) => axis.tooltip).join(", ")}>
        {[0.25, 0.5, 1].map((share) => <polygon key={share} className="web-ring" points={ring(share)} />)}
        {data.axes.map((axis, index) => {
          const [x, y] = point(index, most);
          // The name just past the spoke's end, leaning away from the middle so it stays clear of the web
          const lx = center + (x - center) * 1.14;
          const ly = center + (y - center) * 1.14;
          const anchor = lx < center - 4 ? "end" : lx > center + 4 ? "start" : "middle";
          return (
            <g key={axis.name}>
              <line className="web-spoke" x1={center} y1={center} x2={x} y2={y} />
              <text className="web-name" x={lx} y={ly} textAnchor={anchor}>{axis.name}</text>
            </g>
          );
        })}
        {data.legend && <polygon className="web-before" points={outline(data.axes.map((axis) => axis.before ?? 0))} />}
        <polygon className="web-now" points={outline(data.axes.map((axis) => axis.now))} />
        {data.axes.map((axis, index) => {
          const [x, y] = point(index, axis.now);
          return (
            <circle key={axis.name} className="web-dot" cx={x} cy={y} r={4}>
              <title>{axis.tooltip}</title>
            </circle>
          );
        })}
      </svg>
    </div>
  );
}
