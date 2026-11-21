/** A month (or a year) in review, slide by slide (api/wrapped.py), as stories: each slide on a stage in its
 * picture's color, a bar per slide filling while it shows and turning to the next by itself. The parts of a slide
 * come in one after another, numbers count up and bars grow, and the old slide fades out before the next. The
 * stage itself does not move: a moving window-sized background stutters on the laptop's graphics. */

import { CSSProperties, MouseEvent, useEffect, useRef, useState } from "react";
import { get } from "../api";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Icon, { IconName } from "../components/Icon";
import { useCountUp } from "../components/motion";
import Picture from "../components/Picture";
import Sigil from "../components/Sigil";
import { storyImage } from "../story";
import { useTexts } from "../i18n";
import type { Mood } from "../mood";
import { Column, useOpenDetail } from "../navigation";

type Part =
  | { type: "big"; value: number; kind: "minutes" | "plays" | "new_tracks" | "times" }
  | { type: "chip"; text: string; icon: IconName | "up" | "down" }
  | { type: "record"; src: string }
  | { type: "ring"; src: string; share: number }
  | { type: "bubbles"; items: { src: string; title: string; column: Column; key: string }[] }
  | { type: "clock"; hours: number[]; peak: string; label: string }
  | { type: "calendar"; counts: number[]; columns: number; blank: number; headers: string[] }
  | { type: "podium"; round: boolean; rows: PodiumRow[] }
  | { type: "spotlight"; name: string; family: string; share: string; message: string;
      photos: { src: string; title: string; column: Column; key: string }[];
      others: { family: string; name: string; value: number; text: string }[] }
  | { type: "poster"; month: string; caption: string; artists_caption: string; tracks_caption: string;
      artists: { name: string; key: string; image: string }[]; tracks: { name: string; key: string }[];
      minutes_caption: string; minutes: number; genre_caption: string; genre: string | null; line: string }
  | { type: "heading"; text: string }
  | { type: "text"; text: string; muted: boolean; gap: boolean }
  | { type: "image"; src: string; round: boolean }
  | { type: "columns"; buckets: Bucket[] }
;

interface PodiumRow {
  key: string;
  column: Column;
  title: string;
  subtitle: string;
  value_text: string;
  image: string;
}

interface Slide {
  caption: string;
  parts: Part[];
  mood?: Mood | null;
  /** The covers behind the first slide */
  wall?: string[];
}

interface SummaryData {
  id: string;
  title: string;
  slides: Slide[];
  mood: Mood | null;
}

/** How long a slide shows before the next comes by itself (as on the phone) */
const SLIDE_MS = 9000;

/** A deep violet when the month has no colored cover */
const DEFAULT_HUE = 285;

/** The slide's own picture's hue, else the month's turned a little further each slide so none look alike (as on
 * the phone, wrapped_stage.dart) */
function slideHue(data: SummaryData, index: number): number {
  return data.slides[index].mood?.hue ?? ((data.mood?.hue ?? DEFAULT_HUE) + index * 47) % 360;
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
    : part.kind === "times" ? t("wrapped.times", { count: number(value) })
    : value === 1 ? t("stats.plays_one") : t("stats.plays", { count: number(value) });
  return <span className="wrapped-big">{text}</span>;
}

function Columns({ part, delay }: { part: Extract<Part, { type: "columns" }>; delay: number }) {
  const shown = useShown(delay);
  const buckets = shown ? part.buckets : part.buckets.map((bucket) => ({ ...bucket, value: 0.0001 }));
  return <div className="wrapped-wide"><ColumnChart buckets={buckets} empty="" /></div>;
}


/* The pictures that fill the slides. Only small parts move, and only by transform: the record turns, the rings
 * beat, the bubbles float. Bars, arcs and dots grow in once with CSS and then stand still */

function Chip({ part }: { part: Extract<Part, { type: "chip" }> }) {
  const glyph = part.icon === "up" ? "\u2197" : part.icon === "down" ? "\u2198" : null;
  return (
    <span className="wrapped-chip">
      {glyph ? <span className="wrapped-chip-arrow">{glyph}</span> : <Icon name={part.icon as IconName} />}
      {part.text}
    </span>
  );
}

function Record({ part }: { part: Extract<Part, { type: "record" }> }) {
  return (
    <div className="wrapped-record">
      <div className="record-slide">
        <div className="record-disc">
          <Picture src={part.src} alt="" round className="record-label" />
        </div>
        <div className="record-sheen" />
      </div>
      <Picture src={part.src} alt="" className="record-cover" />
    </div>
  );
}

function Ring({ part }: { part: Extract<Part, { type: "ring" }> }) {
  // The ring's length is its share of the circle: the stroke is dashed to that length and drawn in once
  const radius = 116;
  const length = 2 * Math.PI * radius;
  return (
    <div className="wrapped-ring">
      <span className="ring-beat" />
      <span className="ring-beat late" />
      <svg viewBox="0 0 250 250" className="ring-arc">
        <circle cx="125" cy="125" r={radius} className="ring-track" />
        <circle cx="125" cy="125" r={radius} className="ring-fill"
                style={{ strokeDasharray: `${length * Math.min(1, part.share)} ${length}`, "--ring-length": length } as CSSProperties} />
      </svg>
      <Picture src={part.src} alt="" round className="ring-photo" />
    </div>
  );
}

/** Where each bubble sits (share of the box) and how big it is */
const BUBBLE_SPOTS: [number, number, number][] = [
  [0.5, 0.42, 112], [0.2, 0.22, 76], [0.8, 0.24, 82], [0.14, 0.74, 66],
  [0.86, 0.74, 70], [0.36, 0.92, 54], [0.64, 0.94, 58], [0.5, 0.06, 50],
];

function Bubbles({ part, delay }: { part: Extract<Part, { type: "bubbles" }>; delay: number }) {
  const open = useOpenDetail();
  return (
    <div className="wrapped-bubbles">
      {part.items.slice(0, BUBBLE_SPOTS.length).map((item, index) => {
        const [x, y, size] = BUBBLE_SPOTS[index];
        return (
          <button key={item.key} className="bubble clickable" title={item.title}
                  style={{ left: `calc(${x * 100}% - ${size / 2}px)`, top: `calc(${y * 100}% - ${size / 2}px)`,
                           width: size, height: size, animationDelay: `${delay + index * 90}ms, ${-index * 700}ms` }}
                  onClick={() => open?.(item.column, item.key)}>
            <Picture src={item.src} alt={item.title} round />
          </button>
        );
      })}
    </div>
  );
}

function Clock({ part, delay }: { part: Extract<Part, { type: "clock" }>; delay: number }) {
  const most = Math.max(1, ...part.hours);
  const peak = part.hours.indexOf(Math.max(...part.hours));
  const inner = 62;
  const outer = 112;
  return (
    <div className="wrapped-clock">
      <svg viewBox="-140 -140 280 280">
        <circle r={inner - 7} className="clock-face" />
        {part.hours.map((count, hour) => {
          const angle = (hour / 24) * 360 + 7.5;
          const length = 4 + ((outer - inner - 4) * count) / most;
          return (
            <g key={hour} transform={`rotate(${angle})`}>
              <line y1={-inner} y2={-inner - length} className={hour === peak ? "clock-bar peak" : "clock-bar"}
                    style={{ animationDelay: `${delay + hour * 30}ms` }} />
            </g>
          );
        })}
        {[0, 6, 12, 18].map((hour) => {
          const angle = (hour / 24) * 2 * Math.PI;
          return (
            <text key={hour} x={Math.sin(angle) * (outer + 16)} y={-Math.cos(angle) * (outer + 16)}
                  className="clock-label">{String(hour).padStart(2, "0")}</text>
          );
        })}
      </svg>
      <div className="clock-center">
        <span className="clock-peak">{part.peak}</span>
        <span className="clock-caption">{part.label}</span>
      </div>
    </div>
  );
}

function Calendar({ part, delay }: { part: Extract<Part, { type: "calendar" }>; delay: number }) {
  const cell = 34;
  const most = Math.max(1, ...part.counts);
  const busiest = part.counts.indexOf(most);
  const rows = Math.ceil((part.blank + part.counts.length) / part.columns);
  return (
    <div className="wrapped-calendar">
      {part.headers.length > 0 && (
        <div className="calendar-headers" style={{ gridTemplateColumns: `repeat(${part.columns}, ${cell}px)` }}>
          {part.headers.map((header, index) => <span key={index}>{header}</span>)}
        </div>
      )}
      <svg width={cell * part.columns} height={cell * rows}>
        {part.counts.map((count, index) => {
          const place = part.blank + index;
          const cx = (place % part.columns + 0.5) * cell;
          const cy = (Math.floor(place / part.columns) + 0.5) * cell;
          const style = { animationDelay: `${delay + (index * 600) / part.counts.length}ms` };
          if (!count) return <circle key={index} cx={cx} cy={cy} r={2.5} className="calendar-dot empty" style={style} />;
          return (
            <g key={index} className="calendar-dot" style={style}>
              <circle cx={cx} cy={cy} r={4 + 10 * Math.sqrt(count / most)} opacity={0.35 + (0.6 * count) / most} />
              {index === busiest && <circle cx={cx} cy={cy} r={cell / 2 - 1} className="calendar-ring" />}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** The top three on steps, the first in the middle and highest with a crown, rising from the third; the fourth
 * and fifth come in below */
function Podium({ part, delay }: { part: Extract<Part, { type: "podium" }>; delay: number }) {
  const open = useOpenDetail();
  // Shown left to right: the second, the first, the third, each rising after the one on the next step down
  const order = [1, 0, 2].filter((rank) => rank < part.rows.length);
  const rises = [300, 150, 0];
  return (
    <div className="wrapped-podium">
      <div className="podium-steps">
        {order.map((rank) => {
          const row = part.rows[rank];
          return (
            <button key={row.key} className={`podium-place clickable rank-${rank + 1}`}
                    onClick={() => open?.(row.column, row.key)}>
              <div className="podium-top" style={{ animationDelay: `${delay + rises[rank] + 350}ms` }}>
                {rank === 0 && <span className="podium-crown">{"\u{1F451}"}</span>}
                <Picture src={row.image} alt={row.title} round={part.round} className="podium-picture" />
                <span className="podium-title">{row.title}</span>
                {row.subtitle && <span className="podium-subtitle">{row.subtitle}</span>}
              </div>
              <div className="podium-step" style={{ animationDelay: `${delay + rises[rank]}ms` }}>
                <span className="podium-rank">{rank + 1}</span>
                <span className="podium-value">{row.value_text}</span>
              </div>
            </button>
          );
        })}
      </div>
      <div className="podium-floor" />
      {part.rows.slice(3).map((row, index) => (
        <button key={row.key} className="podium-row clickable" style={{ animationDelay: `${delay + 900 + index * 120}ms` }}
                onClick={() => open?.(row.column, row.key)}>
          <span className="podium-row-rank">{index + 4}</span>
          <Picture src={row.image} alt={row.title} round={part.round} className="podium-row-picture" />
          <span className="podium-row-text">
            <span className="podium-row-title">{row.title}</span>
            {row.subtitle && <span className="podium-subtitle">{row.subtitle}</span>}
          </span>
          <span className="podium-subtitle">{row.value_text}</span>
        </button>
      ))}
    </div>
  );
}

/** The biggest genre in the spotlight: its sigil round its top artist, its other artists, a word to its listener
 * and the next genres */
function Spotlight({ part, delay }: { part: Extract<Part, { type: "spotlight" }>; delay: number }) {
  const open = useOpenDetail();
  const later = (step: number) => ({ animationDelay: `${delay + step}ms` });
  const [top, ...rest] = part.photos;
  return (
    <div className="wrapped-spotlight">
      <div className="spotlight-sigil" style={later(0)}>
        <Sigil family={part.family} size={230}>
          {top && (
            <button className="clickable" title={top.title} onClick={() => open?.(top.column, top.key)}>
              <Picture src={top.src} alt={top.title} round />
            </button>
          )}
        </Sigil>
      </div>
      <span className="spotlight-name reveal" style={later(250)}>{part.name}</span>
      <span className="spotlight-share reveal" style={later(350)}>{part.share}</span>
      {rest.length > 0 && (
        <div className="spotlight-photos">
          {rest.map((photo, index) => (
            <button key={photo.key} className="spotlight-photo clickable" title={photo.title} style={later(500 + index * 120)}
                    onClick={() => open?.(photo.column, photo.key)}>
              <Picture src={photo.src} alt={photo.title} round />
            </button>
          ))}
        </div>
      )}
      <span className="spotlight-message reveal" style={later(850)}>{"\u201C"}{part.message}{"\u201D"}</span>
      {part.others.map((other, index) => (
        <div key={other.name} className="spotlight-other reveal" style={later(1100 + index * 150)}>
          <Sigil family={other.family} size={34} still />
          <span className="spotlight-other-body">
            <span className="spotlight-other-line"><span>{other.name}</span><span className="muted">{other.text}</span></span>
            <span className="spotlight-bar">
              <span style={{ width: `${Math.min(100, other.value)}%`, ...later(1200 + index * 150) }} />
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

/** The month on one card, as the phone's closing poster: the top three's photos, the top five of each, the
 * minutes and the genre, its rows coming in one after another */
function Poster({ part, delay }: { part: Extract<Part, { type: "poster" }>; delay: number }) {
  const open = useOpenDetail();
  const minutes = useCountUp(useShown(delay + 700) ? part.minutes : 0);
  const { number } = useTexts();
  const later = (step: number) => ({ animationDelay: `${delay + step * 90}ms` });
  const [first, second, third] = part.artists;
  const photo = (artist: { name: string; key: string; image: string } | undefined, className: string) =>
    artist && (
      <button className={`poster-photo clickable ${className}`} title={artist.name}
              onClick={() => open?.("artist_key", artist.key)}>
        <Picture src={artist.image} alt={artist.name} round />
      </button>
    );
  const column = (title: string, rows: { name: string; key: string }[], target: Column, start: number) => (
    <div className="poster-column">
      <span className="poster-label reveal" style={later(start)}>{title}</span>
      {rows.map((row, index) => (
        <button key={row.key} className={`poster-row clickable reveal${index === 0 ? " first" : ""}`}
                style={later(start + 1 + index)} onClick={() => open?.(target, row.key)}>
          <span className="poster-rank">{index + 1}</span>
          <span className="poster-name">{row.name}</span>
        </button>
      ))}
    </div>
  );
  return (
    <div className="wrapped-poster">
      <div className="poster-photos">
        {photo(second, "side left")}
        {photo(third, "side right")}
        {photo(first, "main")}
      </div>
      <span className="poster-month reveal" style={later(1)}>{part.month}</span>
      <span className="poster-caption reveal" style={later(1)}>{part.caption}</span>
      <div className="poster-columns">
        {column(part.artists_caption, part.artists, "artist_key", 2)}
        {column(part.tracks_caption, part.tracks, "track_key", 3)}
      </div>
      <div className="poster-numbers reveal" style={later(9)}>
        <span className="poster-number">
          <span className="poster-label">{part.minutes_caption}</span>
          <span className="poster-big">{number(minutes)}</span>
        </span>
        {part.genre && (
          <span className="poster-number">
            <span className="poster-label">{part.genre_caption}</span>
            <span className="poster-genre">{part.genre}</span>
          </span>
        )}
      </div>
      <span className="poster-line reveal" style={later(10)}>{part.line}</span>
    </div>
  );
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
    case "columns":
      content = <Columns part={part} delay={delay} />;
      break;
    case "chip":
      content = <Chip part={part} />;
      break;
    case "record":
      content = <Record part={part} />;
      break;
    case "ring":
      content = <Ring part={part} />;
      break;
    case "bubbles":
      return <Bubbles part={part} delay={delay} />;
    case "clock":
      content = <Clock part={part} delay={delay} />;
      break;
    case "calendar":
      content = <Calendar part={part} delay={delay} />;
      break;
    case "podium":
      return <Podium part={part} delay={delay} />;
    case "spotlight":
      return <Spotlight part={part} delay={delay} />;
    case "poster":
      return <Poster part={part} delay={delay} />;
  }
  return <div className={`reveal${"gap" in part && part.gap ? " gap" : ""}`} style={style}>{content}</div>;
}

/** How long the stage's lights take to drift round once (as on the phone, wrapped_stage.dart) */
const DRIFT_MS = 26000;

/** The stage in one hue with its three soft lights drifting. The lights are drawn once and only moved, so the
 * graphics card shifts them without painting; their clock is shared, so a new stage fading in over the old one
 * has its lights where the old one's are */
function StageLayer({ hue, fade }: { hue: number; fade: boolean }) {
  const [delay] = useState(() => -(performance.now() % DRIFT_MS));
  const style = { "--stage-h": hue } as CSSProperties;
  const light = { animationDelay: `${delay}ms`, animationDuration: `${DRIFT_MS}ms` };
  return (
    <div className={fade ? "stage-layer fade" : "stage-layer"} style={style}>
      <span className="stage-light one" style={light} />
      <span className="stage-light two" style={light} />
      <span className="stage-light three" style={light} />
    </div>
  );
}

/** The month's covers as a tilted wall behind the first slide, darker in the middle under its text */
function CoverWall({ covers }: { covers: string[] }) {
  const rows = 6;
  const perRow = 9;
  return (
    <div className="wrapped-wall" aria-hidden="true">
      <div className="wall-tilt">
        {Array.from({ length: rows }, (_, row) => (
          <div key={row} className="wall-row" style={{ marginLeft: row % 2 ? -60 : 0 }}>
            {Array.from({ length: perRow }, (_, column) => (
              <Picture key={column} src={covers[(row * 3 + column) % covers.length]} alt="" className="wall-cover" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Wrapped({ id, active, onClose, onSeen }: {
  id: string; active: boolean; onClose: () => void; onSeen: () => void;
}) {
  const { t } = useTexts();
  const [data, setData] = useState<SummaryData | null>(null);
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const [paused, setPaused] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  // "Saved" or "Copied" for a moment after sharing
  const [shared, setShared] = useState<string | null>(null);
  const sharing = useRef(false);
  // The slide shown before, whose stage stays under the new one while that fades in
  const [below, setBelow] = useState(0);
  const last = useRef(0);
  useEffect(() => {
    setBelow(last.current);
    last.current = index;
    // Once the new stage covers it, the old one goes, so only one set of lights keeps drifting
    const timer = window.setTimeout(() => setBelow(index), 800);
    return () => window.clearTimeout(timer);
  }, [index]);

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
  // A click on the left third of the stage goes back and anywhere else on, as in stories; rows and buttons that
  // do something of their own are left to it
  const onStage = (event: MouseEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("button, a, .clickable")) return;
    const box = event.currentTarget.getBoundingClientRect();
    step(event.clientX - box.left < box.width / 3 ? -1 : 1);
  };
  // The slide showing as a story picture, saved or copied; the slide holds meanwhile and the picture is taken
  // from the window itself once the menu is gone
  const share = async (kind: "save" | "copy") => {
    setShareOpen(false);
    if (sharing.current) return;
    sharing.current = true;
    const wasPaused = paused;
    setPaused(true);
    try {
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const page = document.querySelector(".page.wrapped")!.getBoundingClientRect();
      const box = document.querySelector(".wrapped-slide")!.getBoundingClientRect();
      let rect;
      if (index === 0) {
        // The first slide with its wall of covers, cut to the story's shape round the slide, to fill the picture
        const stage = document.querySelector(".wrapped-stage")!.getBoundingClientRect();
        const width = Math.min(page.width, (stage.height * 9) / 16);
        const middle = box.left + box.width / 2;
        rect = { left: Math.min(Math.max(page.left, middle - width / 2), page.right - width), top: stage.top,
                 right: 0, bottom: stage.bottom };
        rect.right = rect.left + width;
      } else {
        rect = { left: Math.max(page.left, box.left - 32), top: Math.max(page.top, box.top - 32),
                 right: Math.min(page.right, box.right + 32), bottom: Math.min(page.bottom, box.bottom + 32) };
      }
      const shot = await window.tracker.capture({
        x: Math.round(rect.left), y: Math.round(rect.top),
        width: Math.round(rect.right - rect.left), height: Math.round(rect.bottom - rect.top),
      });
      const story = await storyImage(shot, slideHue(data, index), data.title, index === 0);
      if (kind === "copy") {
        // The picture's bytes from its data address (not fetched, which the page's rules may not allow)
        const bytes = Uint8Array.from(atob(story.split(",")[1]), (char) => char.charCodeAt(0));
        await navigator.clipboard.write([new ClipboardItem({ "image/png": new Blob([bytes], { type: "image/png" }) })]);
        setShared(t("wrapped.share.copied"));
      } else if (await window.tracker.saveImage(`playlist-tracker-${index + 1}.png`, t("wrapped.share.filetype"), story)) {
        setShared(t("wrapped.share.saved"));
      }
      window.setTimeout(() => setShared(null), 2000);
    } finally {
      sharing.current = false;
      setPaused(wasPaused);
    }
  };
  // A page opened from the summary over it holds the slide too, and so does the share menu
  const holding = paused || !active || shareOpen;
  return (
    <div className="page wrapped" style={{ "--stage-h": slideHue(data, index) } as CSSProperties}>
      <div className="stage-back" aria-hidden="true">
        {below !== index && below < count && <StageLayer key={`below${below}`} hue={slideHue(data, below)} fade={false} />}
        <StageLayer key={`stage${index}`} hue={slideHue(data, index)} fade={below !== index} />
      </div>
      <div className="story-bars">
        {data.slides.map((_, bar) => (
          <button key={bar} className="story-bar" aria-label={String(bar + 1)} onClick={() => step(bar - index)}>
            <span key={bar === index ? `fill${index}` : "fill"}
                  className={bar < index ? "story-fill done" : bar === index ? "story-fill" : "story-fill waiting"}
                  style={bar === index ? { animationDuration: `${SLIDE_MS}ms`, animationPlayState: holding ? "paused" : "running" } : undefined}
                  onAnimationEnd={() => step(1)} />
          </button>
        ))}
      </div>
      <header className="toolbar">
        <button className="icon-button" disabled={index === 0} onClick={() => step(-1)}><Icon name="back" /></button>
        <button className="icon-button" disabled={index >= count - 1} onClick={() => step(1)}><Icon name="forward" /></button>
        <h1 className="period-title">{data.title}</h1>
        <span className="spacer" />
        {shared && <span className="wrapped-shared">{shared}</span>}
        <div className="wrapped-share">
          <button className="icon-button" title={t("wrapped.share")} onClick={() => setShareOpen(!shareOpen)}>
            <Icon name="share" />
          </button>
          {shareOpen && (
            <div className="wrapped-share-menu">
              <button onClick={() => share("save")}><Icon name="download" />{t("wrapped.share.save")}</button>
              <button onClick={() => share("copy")}><Icon name="layers" />{t("wrapped.share.copy")}</button>
            </div>
          )}
        </div>
        <button className="icon-button" title={t(paused ? "wrapped.play" : "wrapped.pause")}
                onClick={() => setPaused(!paused)}><Icon name={paused ? "play" : "pause"} /></button>
        <button className="icon-button" onClick={onClose}><Icon name="close" /></button>
      </header>
      {/* Still: a moving wall this big would stutter on the laptop's graphics */}
      {slide.wall && slide.wall.length > 0 && <CoverWall key={index} covers={slide.wall} />}
      <div className={`wrapped-stage${leaving ? " leaving" : ""}`} onClick={onStage}>
        <div key={index} className="wrapped-slide">
          {slide.caption && (
            <div className="reveal wrapped-caption" style={{ animationDelay: `${REVEAL_DELAY_MS}ms` }}>
              {slide.caption.toLocaleUpperCase(document.documentElement.lang || undefined)}
            </div>
          )}
          {slide.parts.map((part, order) => <PartView key={order} part={part} order={order + 1} />)}
        </div>
      </div>
    </div>
  );
}
