import { useTexts } from "../i18n";

export interface Bucket {
  label: string;
  value: number;
  tooltip: string;
}

/** The previous period's column at the same place, and the names of the two for the legend */
export interface Comparison {
  previous: (Omit<Bucket, "label"> | null)[];
  legend: { current: string; previous: string };
}

/** Columns with their labels under them; labels are thinned out when there are many columns. Given the previous
 * period, each column has its grey column beside it, on the same scale, under a legend of the two. */
export default function ColumnChart({ buckets, empty, comparison, values = false }: {
  buckets: Bucket[]; empty: string; comparison?: Comparison | null;
  /** Each column's number over it, when there are few enough columns for them to fit */
  values?: boolean;
}) {
  const { number } = useTexts();
  const previous = comparison?.previous ?? [];
  const most = Math.max(...buckets.map((bucket) => bucket.value), ...previous.map((bucket) => bucket?.value ?? 0), 0);
  if (!most) return <p className="empty chart-empty">{empty}</p>;
  const every = buckets.length > 16 ? Math.ceil(buckets.length / 12) : 1;
  const numbered = values && buckets.length <= 12;
  const columns = (
    <div className={`columns${comparison ? " compared" : ""}${numbered ? " numbered" : ""}`} style={{ gridTemplateColumns: `repeat(${buckets.length}, 1fr)` }}>
      {buckets.map((bucket, index) => {
        const before = previous[index];
        return (
          <div key={index} className="column"
               title={before ? `${bucket.tooltip}\n\n${comparison!.legend.previous}\n${before.tooltip}` : bucket.tooltip}>
            <div className="column-space">
              {comparison && (
                <div className="column-fill previous" style={{ height: before ? `${(before.value * 100) / most}%` : 0 }}>
                  {numbered && before && <span className="column-value">{number(before.value)}</span>}
                </div>
              )}
              <div className="column-fill" style={{ height: `${(bucket.value * 100) / most}%` }}>
                {numbered && <span className="column-value">{number(bucket.value)}</span>}
              </div>
            </div>
            <span className="column-label">{index % every === 0 ? bucket.label : ""}</span>
          </div>
        );
      })}
    </div>
  );
  if (!comparison) return columns;
  return (
    <>
      <div className="legend">
        <span className="legend-item"><span className="swatch current" />{comparison.legend.current}</span>
        <span className="legend-item"><span className="swatch previous" />{comparison.legend.previous}</span>
      </div>
      {columns}
    </>
  );
}
