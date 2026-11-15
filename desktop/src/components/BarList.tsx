import { Column, useOpenDetail } from "../navigation";
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
  /** The page a row opens when it names its own (a track not heard yet has null and opens nothing) */
  column?: Column | null;
}

/** Rows with a bar as long as their value, optionally ranked and with a picture; bars grow to new values.
 * A click on a row opens its page: column names the kind of all rows, or each row names its own. */
export default function BarList({ rows, empty, round = false, column }: {
  rows: BarRow[]; empty: string; round?: boolean; column?: Column;
}) {
  const open = useOpenDetail();
  if (!rows.length) return <p className="empty">{empty}</p>;
  const most = Math.max(...rows.map((row) => row.value), 1);
  const ranked = rows.some((row) => row.rank !== undefined);
  const pictures = rows.some((row) => row.image);
  const changes = rows.some((row) => row.change !== undefined);
  const columns = [ranked && "24px", pictures && "40px", "1fr", "44px", changes && "46px"].filter(Boolean).join(" ");
  return (
    <ol className={`bar-list${pictures ? "" : " compact"}`}>
      {rows.map((row) => {
        const target = row.column === undefined ? column : row.column;
        const clickable = Boolean(open && target);
        return (
          <li key={row.key} className={`bar-row${clickable ? " clickable" : ""}`}
              style={{ gridTemplateColumns: columns }}
              title={`${row.title}\n${row.subtitle}\n${row.detail}${row.change ? `\n${row.change.long}` : ""}`}
              onClick={clickable ? () => open!(target!, row.key) : undefined}>
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
        );
      })}
    </ol>
  );
}
