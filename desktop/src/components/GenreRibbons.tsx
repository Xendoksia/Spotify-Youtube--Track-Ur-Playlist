import { useState } from "react";
import { Point, smooth } from "./DayCurve";
import type { StackedColumn } from "./StackedColumns";

const WIDTH = 640;
const HEIGHT = 190;
// Room for the ranks on the left, the genres' names on the right and the columns' labels under the lines
const LEFT = 22;
const RIGHT = 150;
const TOP = 22;
const BOTTOM = 34;

/** The main genres' places in each column (the day of a week, the week of a month, the month of a year) as thick
 * ribbons in their colors, the first place at the top, so a genre that overtakes another crosses over it. Columns
 * without a known genre are passed over; the names stand at the ribbons' ends with the genre's share of the period,
 * and each column's shares show under the pointer. */
export default function GenreRibbons({ columns, legend, empty }: {
  columns: StackedColumn[]; legend: { series: number | "other"; text: string }[]; empty: string;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const series = legend.flatMap((item) => (item.series === "other" ? [] : [item]));
  const heard = columns.flatMap((column, index) => (column.segments.length ? [index] : []));
  if (!series.length || !heard.length) return <p className="empty chart-empty">{empty}</p>;
  const plot = WIDTH - LEFT - RIGHT;
  const x = (index: number) => LEFT + ((index + 0.5) / columns.length) * plot;
  const row = series.length > 1 ? (HEIGHT - TOP - BOTTOM) / (series.length - 1) : 0;
  const y = (place: number) => TOP + place * row;
  // Each heard column's order of the genres, the biggest share first (the bigger genre of the period on a tie)
  const places = new Map<number, number[]>();
  for (const index of heard) {
    const share = (name: number) => columns[index].segments.find((segment) => segment.series === name)?.share ?? 0;
    const order = series.map((item) => item.series as number).sort((a, b) => share(b) - share(a) || a - b);
    places.set(index, order);
  }
  const placeOf = (name: number, index: number) => places.get(index)!.indexOf(name);
  const every = columns.length > 16 ? Math.ceil(columns.length / 12) : 1;
  const last = heard[heard.length - 1];
  const slot = plot / columns.length;
  return (
    <div className="genre-ribbons" onMouseLeave={() => setHovered(null)}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={series.map((item) => item.text).join(", ")}>
        {series.map((_, place) => (
          <text key={place} className="ribbon-place" x={LEFT - 10} y={y(place)}>{place + 1}</text>
        ))}
        {hovered !== null && (
          <rect className="ribbon-column" x={LEFT + hovered * slot} y={TOP - 14} width={slot}
                height={HEIGHT - TOP - BOTTOM + 28} rx={6} />
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
        {series.map((item) => (
          <text key={item.series} className="ribbon-name" x={x(last) + 14} y={y(placeOf(item.series as number, last))}>
            {item.text}
          </text>
        ))}
        {columns.map((column, index) => index % every === 0 && (
          <text key={index} className="ribbon-label" x={x(index)} y={HEIGHT - 8}>{column.label}</text>
        ))}
        {columns.map((column, index) => (
          <rect key={index} className="ribbon-hit" x={LEFT + index * slot} y={0} width={slot} height={HEIGHT}
                onMouseEnter={() => setHovered(index)}>
            <title>{column.tooltip}</title>
          </rect>
        ))}
      </svg>
    </div>
  );
}
