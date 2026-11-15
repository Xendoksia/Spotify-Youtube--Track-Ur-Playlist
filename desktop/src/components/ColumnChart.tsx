export interface Bucket {
  label: string;
  value: number;
  tooltip: string;
}

/** Columns with their labels under them; labels are thinned out when there are many columns. */
export default function ColumnChart({ buckets, empty }: { buckets: Bucket[]; empty: string }) {
  const most = Math.max(...buckets.map((bucket) => bucket.value), 0);
  if (!most) return <p className="empty chart-empty">{empty}</p>;
  const every = buckets.length > 16 ? Math.ceil(buckets.length / 12) : 1;
  return (
    <div className="columns" style={{ gridTemplateColumns: `repeat(${buckets.length}, 1fr)` }}>
      {buckets.map((bucket, index) => (
        <div key={index} className="column" title={bucket.tooltip}>
          <div className="column-space">
            <div className="column-fill" style={{ height: `${(bucket.value * 100) / most}%` }} />
          </div>
          <span className="column-label">{index % every === 0 ? bucket.label : ""}</span>
        </div>
      ))}
    </div>
  );
}
