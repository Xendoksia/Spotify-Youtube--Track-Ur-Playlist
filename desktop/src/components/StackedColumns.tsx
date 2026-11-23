/** Columns that each fill to 100%, split into the shares of a few series (the genres over time). */

export type Series = number | "other";

export interface StackedColumn {
  label: string;
  tooltip: string;
  segments: { series: Series; share: number }[];
}

export const seriesClass = (series: Series) => `series-${series}`;

export default function StackedColumns({ columns, empty }: { columns: StackedColumn[]; empty: string }) {
  if (!columns.length) return <p className="empty chart-empty">{empty}</p>;
  const every = columns.length > 16 ? Math.ceil(columns.length / 12) : 1;
  return (
    <div className="columns" style={{ gridTemplateColumns: `repeat(${columns.length}, 1fr)` }}>
      {columns.map((column, index) => (
        <div key={index} className="column" title={column.tooltip}>
          <div className="column-space stacked">
            {column.segments.map((segment) => (
              <div key={segment.series} className={`segment ${seriesClass(segment.series)}`}
                   style={{ height: `${segment.share * 100}%` }} />
            ))}
          </div>
          <span className="column-label">{index % every === 0 ? column.label : ""}</span>
        </div>
      ))}
    </div>
  );
}
