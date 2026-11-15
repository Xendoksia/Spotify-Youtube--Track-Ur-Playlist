import { useTexts } from "../i18n";
import { useCountUp } from "./motion";
import Sparkline, { TrendPoint } from "./Sparkline";

export interface TileData {
  name: string;
  label: string;
  value: number;
  text: string;
  /** Numbers and durations count up to new values; dates and names ("text") are shown as they are */
  kind: "number" | "duration" | "text";
  delta?: { text: string; kind: "up" | "down" | "same" } | null;
  /** The value per day (or month) of the period, drawn as a line under it */
  trend?: TrendPoint[];
}

export default function Tile({ tile }: { tile: TileData }) {
  const { number, duration } = useTexts();
  const shown = useCountUp(tile.kind === "text" ? 0 : tile.value);
  const value = tile.kind === "text" ? tile.text
    : tile.kind === "duration" ? (tile.value ? duration(shown) : tile.text) : number(shown);
  return (
    <section className="tile">
      <span className="tile-label">{tile.label}</span>
      <span className={`tile-value${tile.kind === "text" ? " text" : ""}`} title={tile.kind === "text" ? tile.text : undefined}>
        {value}
      </span>
      {tile.delta !== undefined && (
        <span className={`tile-delta delta-${tile.delta?.kind ?? "none"}`}>{tile.delta?.text ?? " "}</span>
      )}
      {tile.trend && <Sparkline points={tile.trend} />}
    </section>
  );
}
