import { useEffect, useRef, useState } from "react";
import { Point, smooth } from "./DayCurve";
import { seriesClass, StackedColumn } from "./StackedColumns";

// Room for the places on the left and the columns' labels under the lines, in pixels
const LEFT = 26;
const RIGHT = 14;
const TOP = 14;
const BOTTOM = 34;
// As tall as this at least, else as tall as the card beside it lets it be
const MIN_HEIGHT = 190;

/** The size of an element, followed as it changes */
function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

/** The main genres' places in each column (the day of a week, the week of a month, the month of a year) as thick
 * ribbons in their colors, the first place at the top, so a genre that overtakes another crosses over it. The
 * columns from the first to the last with a known genre are drawn and empty ones between them passed over; the
 * legend over them names the genres with their share of the period, and each column's shares show under the
 * pointer. The drawing fills the card, in pixels so its text keeps its size. Only on the desktop: the phone keeps
 * the stacked columns, as the ribbons were too cramped there. */
export default function GenreRibbons({ columns: all, legend, empty }: {
  columns: StackedColumn[]; legend: { series: number | "other"; text: string }[]; empty: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [box, size] = useSize<HTMLDivElement>();
  const series = legend.flatMap((item) => (item.series === "other" ? [] : [item]));
  const known = all.flatMap((column, index) => (column.segments.length ? [index] : []));
  if (!series.length || !known.length) return <p className="empty chart-empty">{empty}</p>;
  const columns = all.slice(known[0], known[known.length - 1] + 1);
  const heard = known.map((index) => index - known[0]);
  const width = size.width;
  const height = Math.max(size.height, MIN_HEIGHT);
  const slot = (width - LEFT - RIGHT) / columns.length;
  const x = (index: number) => LEFT + (index + 0.5) * slot;
  const row = series.length > 1 ? (height - TOP - BOTTOM) / (series.length - 1) : 0;
  const y = (place: number) => TOP + place * row;
  // Each heard column's order of the genres, the biggest share first (the bigger genre of the period on a tie)
  const places = new Map<number, number[]>();
  for (const index of heard) {
    const share = (name: number) => columns[index].segments.find((segment) => segment.series === name)?.share ?? 0;
    places.set(index, series.map((item) => item.series as number).sort((a, b) => share(b) - share(a) || a - b));
  }
  const placeOf = (name: number, index: number) => places.get(index)!.indexOf(name);
  // Labels about 70 pixels apart at least, so they do not run together
  const every = Math.max(1, Math.ceil(70 / Math.max(slot, 1)));
  return (
    <>
      <div className="legend">
        {series.map((item) => (
          <span key={item.series} className="legend-item">
            <span className={`swatch ${seriesClass(item.series)}`} />
            {item.text}
          </span>
        ))}
      </div>
      <div className="genre-ribbons" ref={box} onMouseLeave={() => setHovered(null)}>
        {width > 0 && (
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
               aria-label={series.map((item) => item.text).join(", ")}>
            {series.map((_, place) => (
              <text key={place} className="ribbon-place" x={LEFT - 12} y={y(place)}>{place + 1}</text>
            ))}
            {hovered !== null && (
              <rect className="ribbon-column" x={LEFT + hovered * slot} y={TOP - 12} width={slot}
                    height={height - TOP - BOTTOM + 24} rx={6} />
            )}
            {series.map((item) => {
              const name = item.series as number;
              const points: Point[] = heard.map((index) => [x(index), y(placeOf(name, index))]);
              return (
                <g key={name} className={`ribbon ribbon-${name}`}>
                  {points.length > 1 && (
                    <path d={smooth([points[0], ...points, points[points.length - 1]])} pathLength={1} />
                  )}
                  {points.map(([px, py], i) => <circle key={i} cx={px} cy={py} r={hovered === heard[i] ? 7 : 5} />)}
                </g>
              );
            })}
            {columns.map((column, index) => index % every === 0 && (
              <text key={index} className="ribbon-label" x={x(index)} y={height - 10}>{column.label}</text>
            ))}
            {columns.map((column, index) => (
              <rect key={index} className="ribbon-hit" x={LEFT + index * slot} y={0} width={slot} height={height}
                    onMouseEnter={() => setHovered(index)}>
                <title>{column.tooltip}</title>
              </rect>
            ))}
          </svg>
        )}
      </div>
    </>
  );
}
