import Change, { RankChange } from "./Change";
import Picture from "./Picture";

export interface BarRow {
  key: string;
  rank?: number;
  title: string;
  subtitle: string;
  value: number;
  value_text: string;
  detail: string;
  change?: RankChange | null;
  image?: string;
}

/** Rows with a bar as long as their value, optionally ranked and with a picture; bars grow to new values. */
export default function BarList({ rows, empty, round = false }: { rows: BarRow[]; empty: string; round?: boolean }) {
  if (!rows.length) return <p className="empty">{empty}</p>;
  const most = Math.max(...rows.map((row) => row.value), 1);
  const ranked = rows.some((row) => row.rank !== undefined);
  const pictures = rows.some((row) => row.image);
  const changes = rows.some((row) => row.change !== undefined);
  const columns = [ranked && "24px", pictures && "40px", "1fr", "44px", changes && "36px"].filter(Boolean).join(" ");
  return (
    <ol className={`bar-list${pictures ? "" : " compact"}`}>
      {rows.map((row) => (
        <li key={row.key} className="bar-row" style={{ gridTemplateColumns: columns }}
            title={`${row.title}\n${row.subtitle}\n${row.detail}`}>
          {ranked && <span className="rank">{row.rank}</span>}
          {pictures && <Picture src={row.image ?? ""} alt={row.title} round={round} className="bar-picture" />}
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
          {changes && <span className="bar-change"><Change change={row.change ?? null} /></span>}
        </li>
      ))}
    </ol>
  );
}
