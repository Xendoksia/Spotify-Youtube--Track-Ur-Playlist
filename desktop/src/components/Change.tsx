/** A rank's change since the previous period: ▲2, ▼1, =, NEW or ↺ (api/overview.py rank_changes). */

export interface RankChange {
  kind: "up" | "down" | "same" | "new" | "back";
  short: string;
  long: string;
}

function Mark({ kind }: { kind: RankChange["kind"] }) {
  if (kind === "up" || kind === "down") {
    return (
      <svg viewBox="0 0 10 10" aria-hidden>
        <path d={kind === "up" ? "M2 6.5 5 3.5 8 6.5" : "M2 3.5 5 6.5 8 3.5"} />
      </svg>
    );
  }
  if (kind === "back") {
    return (
      <svg viewBox="0 0 10 10" aria-hidden>
        <path d="M2.2 5a2.8 2.8 0 1 0 .9-2.1M2.2 1.6v1.6h1.6" />
      </svg>
    );
  }
  return null;
}

/** The change as a small colored pill; on number one cards (long) followed by what it means. */
export default function Change({ change, long = false }: { change: RankChange | null; long?: boolean }) {
  if (!change) return null;
  const label = change.kind === "up" || change.kind === "down" ? change.short.slice(1)
    : change.kind === "same" ? "–" : change.kind === "new" ? change.short : "";
  const pill = (
    <span className={`change change-${change.kind}`} title={long ? undefined : change.long}>
      <Mark kind={change.kind} />
      {label}
    </span>
  );
  if (!long) return pill;
  // The long text repeats the short one first ("▲2 (#3 in the previous period)"), which the pill already shows
  const note = (change.long.startsWith(change.short) ? change.long.slice(change.short.length) : change.long)
    .trim().replace(/^\((.*)\)$/, "$1");
  return (
    <span className="change-long">
      {pill}
      {note}
    </span>
  );
}
