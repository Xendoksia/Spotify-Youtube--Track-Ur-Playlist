/** A month (or a year) in review, slide by slide (api/wrapped.py): the parts of a slide come in one after
 * another, numbers count up and bars grow, and the old slide fades out before the next. */

import { useEffect, useState } from "react";
import { get } from "../api";
import BarList, { BarRow } from "../components/BarList";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Icon from "../components/Icon";
import { useCountUp } from "../components/motion";
import Picture from "../components/Picture";
import { useTexts } from "../i18n";

type Part =
  | { type: "big"; value: number; kind: "minutes" | "plays" | "new_tracks" }
  | { type: "heading"; text: string }
  | { type: "text"; text: string; muted: boolean; gap: boolean }
  | { type: "image"; src: string; round: boolean }
  | { type: "list"; rows: BarRow[]; round: boolean }
  | { type: "columns"; buckets: Bucket[] }
  | { type: "genre"; name: string; value: number; first: boolean }
  | { type: "tiles"; tiles: { caption: string; value: string }[] };

interface Slide {
  caption: string;
  parts: Part[];
}

interface SummaryData {
  id: string;
  title: string;
  slides: Slide[];
}

// The old slide fades out, then the parts of the new one come in one after another (as the Tk window)
const FADE_OUT_MS = 180;
const REVEAL_DELAY_MS = 60;
const REVEAL_STEP_MS = 110;

/** True once the part's turn to appear came */
function useShown(delay: number): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setShown(true), delay);
    return () => window.clearTimeout(timer);
  }, [delay]);
  return shown;
}

function Big({ part, delay }: { part: Extract<Part, { type: "big" }>; delay: number }) {
  const { t, number } = useTexts();
  const shown = useCountUp(useShown(delay) ? part.value : 0);
  const value = Math.round(shown);
  const text = part.kind === "minutes" ? t("wrapped.minutes", { minutes: number(value) })
    : part.kind === "new_tracks" ? t("wrapped.new_tracks", { count: number(value) })
    : value === 1 ? t("stats.plays_one") : t("stats.plays", { count: number(value) });
  return <span className="wrapped-big">{text}</span>;
}

function Genre({ part, delay }: { part: Extract<Part, { type: "genre" }>; delay: number }) {
  const { t } = useTexts();
  const shown = useCountUp(useShown(delay) ? part.value : 0);
  return (
    <span className={part.first ? "wrapped-big" : "wrapped-name muted"}>
      {part.name}  {t("stats.percent", { value: Math.round(shown) })}
    </span>
  );
}

function List({ part, delay }: { part: Extract<Part, { type: "list" }>; delay: number }) {
  // The bars grow from nothing once the list appears
  const shown = useShown(delay);
  const rows = shown ? part.rows : part.rows.map((row) => ({ ...row, value: 0 }));
  return <div className="wrapped-wide"><BarList rows={rows} empty="" round={part.round} /></div>;
}

function Columns({ part, delay }: { part: Extract<Part, { type: "columns" }>; delay: number }) {
  const shown = useShown(delay);
  const buckets = shown ? part.buckets : part.buckets.map((bucket) => ({ ...bucket, value: 0.0001 }));
  return <div className="wrapped-wide"><ColumnChart buckets={buckets} empty="" /></div>;
}

function PartView({ part, order }: { part: Part; order: number }) {
  const delay = REVEAL_DELAY_MS + order * REVEAL_STEP_MS;
  const style = { animationDelay: `${delay}ms` };
  let content;
  switch (part.type) {
    case "big":
      content = <Big part={part} delay={delay} />;
      break;
    case "heading":
      content = <span className="wrapped-name">{part.text}</span>;
      break;
    case "text":
      content = <span className={part.muted ? "wrapped-text muted" : "wrapped-text"}>{part.text}</span>;
      break;
    case "image":
      content = <Picture src={part.src} alt="" round={part.round} className="wrapped-picture" />;
      break;
    case "list":
      content = <List part={part} delay={delay} />;
      break;
    case "columns":
      content = <Columns part={part} delay={delay} />;
      break;
    case "genre":
      content = <Genre part={part} delay={delay} />;
      break;
    case "tiles":
      return (
        <div className="wrapped-tiles">
          {part.tiles.map((tile, index) => (
            // The tiles come in one after another
            <div key={index} className="tile reveal" style={{ animationDelay: `${delay + (index * REVEAL_STEP_MS) / 2}ms` }}>
              <span className="tile-label">{tile.caption}</span>
              <span className="wrapped-tile-value">{tile.value}</span>
            </div>
          ))}
        </div>
      );
  }
  return <div className={`reveal${"gap" in part && part.gap ? " gap" : ""}`} style={style}>{content}</div>;
}

export default function Wrapped({ id, active, onClose, onSeen }: {
  id: string; active: boolean; onClose: () => void; onSeen: () => void;
}) {
  const [data, setData] = useState<SummaryData | null>(null);
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    setData(null);
    setIndex(0);
    get<SummaryData>("/api/wrapped", { id }).then((result) => {
      setData(result);
      onSeen();
    }, () => onClose());
  }, [id, onClose, onSeen]);

  const count = data?.slides.length ?? 0;
  const step = (direction: number) => {
    const next = index + direction;
    if (leaving || next < 0 || next >= count) return;
    setLeaving(true);
    window.setTimeout(() => {
      setIndex(next);
      setLeaving(false);
    }, FADE_OUT_MS);
  };

  // Left and right move between the slides, Esc closes the summary (not while a page opened from it is over it)
  useEffect(() => {
    if (!active) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      else if (event.key === "ArrowRight") step(1);
      else if (event.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!data) return null;
  const slide = data.slides[index];
  return (
    <div className="page wrapped">
      <header className="toolbar">
        <button className="icon-button" disabled={index === 0} onClick={() => step(-1)}><Icon name="back" /></button>
        <button className="icon-button" disabled={index >= count - 1} onClick={() => step(1)}><Icon name="forward" /></button>
        <h1 className="period-title">{data.title}</h1>
        <span className="spacer" />
        <div className="dots">
          {data.slides.map((_, dot) => (
            <button key={dot} className={dot === index ? "dot selected" : "dot"} aria-label={String(dot + 1)}
                    onClick={() => step(dot - index)} />
          ))}
        </div>
        <button className="icon-button" onClick={onClose}><Icon name="close" /></button>
      </header>
      <div className={`wrapped-stage${leaving ? " leaving" : ""}`}>
        <div key={index} className="wrapped-slide">
          <div className="reveal wrapped-caption" style={{ animationDelay: `${REVEAL_DELAY_MS}ms` }}>
            {slide.caption.toLocaleUpperCase(document.documentElement.lang || undefined)}
          </div>
          {slide.parts.map((part, order) => <PartView key={order} part={part} order={order + 1} />)}
        </div>
      </div>
    </div>
  );
}
