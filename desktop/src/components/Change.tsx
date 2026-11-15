/** A rank's change since the previous period: ▲2, ▼1, =, NEW or ↺ (api/overview.py rank_changes). */

export interface RankChange {
  kind: "up" | "down" | "same" | "new" | "back";
  short: string;
  long: string;
}

export default function Change({ change, long = false }: { change: RankChange | null; long?: boolean }) {
  if (!change) return null;
  return (
    <span className={`change change-${change.kind}`} title={long ? undefined : change.long}>
      {long ? change.long : change.short}
    </span>
  );
}
