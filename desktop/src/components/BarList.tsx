import Change, { RankChange } from "./Change";
import Picture from "./Picture";

export interface BarRow {
  key: string;
  rank: number;
  title: string;
  subtitle: string;
  value: number;
  value_text: string;
  detail: string;
  change: RankChange | null;
  image: string;
}

/** Ranked rows with a picture and a bar as long as the plays; bars grow to new values as the period changes. */
export default function BarList({ rows, empty, round = false }: { rows: BarRow[]; empty: string; round?: boolean }) {
  if (!rows.length) return <p className="empty">{empty}</p>;
  const most = Math.max(...rows.map((row) => row.value), 1);
  return (
    <ol className="bar-list">
      {rows.map((row) => (
        <li key={row.key} className="bar-row" title={`${row.title}\n${row.subtitle}\n${row.detail}`}>
          <span className="rank">{row.rank}</span>
          <Picture src={row.image} alt={row.title} round={round} className="bar-picture" />
          <div className="bar-body">
            <div className="bar-text">
              <span className="bar-title">{row.title}</span>
              <span className="bar-subtitle">{row.subtitle}</span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${(row.value * 100) / most}%` }} />
            </div>
          </div>
          <span className="bar-value">{row.value_text}</span>
          <span className="bar-change"><Change change={row.change} /></span>
        </li>
      ))}
    </ol>
  );
}
