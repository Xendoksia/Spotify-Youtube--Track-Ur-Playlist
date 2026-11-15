import { useOpenDetail } from "../navigation";
import { BarRow } from "./BarList";
import Picture from "./Picture";

/** A longer list of tracks on a page of its own (an artist's most played, an album's tracks), two to a row: the
 * number, the cover, the name over its album or length, the plays, and a thin line as long as the plays. Rows
 * with a column open their track; a track not heard yet is muted. */
export default function TrackGrid({ rows, empty }: { rows: BarRow[]; empty: string }) {
  const open = useOpenDetail();
  if (!rows.length) return <p className="empty">{empty}</p>;
  const most = Math.max(...rows.map((row) => row.value), 1);
  const pictures = rows.some((row) => row.image);
  return (
    <ol className={`track-grid${pictures ? " with-pictures" : ""}`}>
      {rows.map((row, index) => {
        const clickable = Boolean(open && row.column);
        return (
          <li key={row.key}
              className={`track-item${clickable ? " clickable" : ""}${row.value ? "" : " unheard"}`}
              title={`${row.title}${row.subtitle ? `\n${row.subtitle}` : ""}\n${row.detail}`}
              onClick={clickable ? () => open!(row.column!, row.key) : undefined}>
            <span className="track-number">{row.rank ?? index + 1}</span>
            {pictures && <Picture src={row.image ?? ""} alt={row.title} className="track-picture" />}
            <span className="track-text">
              <span className="track-title">{row.title}</span>
              {row.subtitle && <span className="track-subtitle">{row.subtitle}</span>}
            </span>
            <span className="track-value">{row.value_text}</span>
            <span className="track-share" style={{ width: `${(row.value * 100) / most}%` }} />
          </li>
        );
      })}
    </ol>
  );
}
