/** A strip along the bottom of the window with the song playing in the Spotify app: cover, title, artist, the
 * time into the song with a progress line, and whether the play is recorded yet, tinted with the cover's color.
 * A click opens the song large (NowPlayingView); from there a recorded song opens its page. */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { imageUrl } from "../api";
import { useTexts } from "../i18n";
import { moodStyle } from "../mood";
import { clock, NowPlaying, useNowPlaying } from "../nowPlaying";
import Icon from "./Icon";
import Picture from "./Picture";

function progress(play: NonNullable<NowPlaying["play"]>) {
  const { position, duration } = play;
  return {
    time: position !== null && duration ? `${clock(position)} / ${clock(duration)}` : position !== null ? clock(position) : "",
    share: position !== null && duration ? Math.min(1, position / duration) : 0,
  };
}

/** "Playing" or "Paused" without the symbol the texts start with, as the equalizer shows it */
function stateText(t: (key: string) => string, playing: boolean) {
  return t(playing ? "mini.playing" : "mini.paused").replace(/^\S+\s+/, "");
}

/** Three bars that dance while the song plays and rest when it is paused */
function Equalizer({ playing }: { playing: boolean }) {
  return (
    <span className={`equalizer${playing ? " playing" : ""}`} aria-hidden>
      <span /><span /><span />
    </span>
  );
}

// The cover flies between the strip and the middle on the compositor, so no frame waits for layout or paint. The
// view fades in its parts, never the whole of it, and the shade over the window only briefly: while a layer the
// size of the window is see-through, the page under it is drawn again for every frame, which on the laptop's
// graphics took longer than a frame at 144 Hz. Once the shade is opaque the page is left out.
const FLY_MS = 420;
const SHADE_MS = 120;
const PARTS = ".now-view-backdrop, .now-view-close, .now-view-body > :not(.now-view-cover)";
const FLY_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

/** The move that puts an element lying at `to` where `from` is */
function offset(from: DOMRect, to: DOMRect) {
  return `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${from.width / to.width})`;
}

/** The cover drawn small and softened once on a canvas the size of a stamp, then stretched over the window: as
 * blurred as the 70 px CSS blur of the whole window was, which had to be drawn again for frames of the opening */
function Backdrop({ src }: { src: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const image = new Image();
    image.onload = () => {
      const context = canvas.current?.getContext("2d");
      if (!context) return;
      context.clearRect(0, 0, 48, 48);
      context.filter = "blur(3px) saturate(1.3)";
      // Drawn larger than the canvas so the blur does not fade out at the edges
      context.drawImage(image, -8, -8, 64, 64);
      canvas.current!.classList.add("drawn");
    };
    image.src = imageUrl(src);
  }, [src]);
  return <canvas ref={canvas} className="now-view-backdrop" width={48} height={48} />;
}

function NowPlayingView({ now, from, close, openTrack }: {
  now: NowPlaying; from: () => DOMRect | null; close: () => void; openTrack: (key: string) => void;
}) {
  const { t } = useTexts();
  const play = now.play!;
  const playing = now.state === "playing";
  const { share } = progress(play);
  const view = useRef<HTMLDivElement>(null);
  const firstKey = useRef(play.key);
  const leaving = useRef(false);

  // Opening: the cover grows out of the strip's while the rest fades in
  useLayoutEffect(() => {
    const cover = view.current?.querySelector<HTMLElement>(".now-view-cover");
    const start = from();
    if (!cover || !start || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    cover.animate([{ transform: offset(start, cover.getBoundingClientRect()) }, { transform: "none" }],
                  { duration: FLY_MS, easing: FLY_EASING });
  }, [from]);

  // Closing: the view fades and the cover flies back into the strip before the view goes
  const leave = useCallback(() => {
    const root = view.current;
    if (leaving.current || !root) return;
    leaving.current = true;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return close();
    root.classList.add("leaving");
    const cover = root.querySelector<HTMLElement>(".now-view-cover");
    const end = from();
    if (cover && end) {
      cover.animate([{ transform: "none" }, { transform: offset(end, cover.getBoundingClientRect()) }],
                    { duration: FLY_MS * 0.8, easing: FLY_EASING, fill: "forwards" });
    }
    const fadeMs = FLY_MS * 0.8 - SHADE_MS;
    for (const part of root.querySelectorAll<HTMLElement>(PARTS)) {
      part.animate([{ opacity: getComputedStyle(part).opacity }, { opacity: 0 }], { duration: fadeMs, easing: "ease-in", fill: "forwards" });
    }
    // The cover fades only at the end of its way, into the strip's, as the shade goes last
    cover?.animate([{ opacity: 1 }, { opacity: 1, offset: 0.7 }, { opacity: 0 }], { duration: FLY_MS * 0.8, fill: "forwards" });
    const shade = root.querySelector<HTMLElement>(".now-view-shade");
    if (!shade) return close();
    shade.animate([{ opacity: 1 }, { opacity: 0 }], { duration: SHADE_MS, delay: fadeMs, easing: "ease-out", fill: "forwards" })
      .finished.then(close, close);
  }, [close, from]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && leave();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [leave]);
  return (
    <div ref={view} className={`now-view${play.mood ? " has-mood" : ""}`} style={moodStyle(play.mood)} onClick={leave}>
      <div className="now-view-shade" />
      <Backdrop src={play.image} />
      <button className="icon-button now-view-close" onClick={leave} aria-label="Esc"><Icon name="close" /></button>
      <div className="now-view-body" onClick={(event) => event.stopPropagation()}>
        <span className="now-view-caption"><Equalizer playing={playing} />{t("mini.now")}</span>
        {/* Keyed by the song: the first one flies in from the strip, one starting while the view is open slides in */}
        <div key={play.key} className={`now-view-cover${play.key !== firstKey.current ? " next" : ""}`}>
          <Picture src={play.image} alt={play.name} eager />
        </div>
        <div key={`${play.key}-text`} className="now-view-text">
          <span className="now-view-title">{play.name}</span>
          <span className="now-view-artist">{play.artist}</span>
          {play.album && <span className="now-view-album">{play.album}</span>}
        </div>
        <div className="now-view-progress">
          <div className="mini-progress">
            <div className={`mini-progress-fill${playing ? " moving" : ""}`} style={{ transform: `scaleX(${share})` }} />
          </div>
          <div className="now-view-times">
            <span>{play.position !== null ? clock(play.position) : ""}</span>
            <span>{play.duration ? clock(play.duration) : ""}</span>
          </div>
        </div>
        <span className="now-view-state">
          {stateText(t, playing)}  ·  {t("mini.heard", { listened: play.listened })}
          {play.recorded ? t("mini.recorded") : ""}
        </span>
        {play.recorded && (
          <button className="button accent" onClick={() => {
            close();
            openTrack(play.key);
          }}>
            {t("mini.open_page")}
          </button>
        )}
      </div>
    </div>
  );
}

export default function MiniPlayer({ openTrack }: { openTrack: (key: string) => void }) {
  const { t } = useTexts();
  const now = useNowPlaying();
  const [open, setOpen] = useState(false);
  const strip = useRef<HTMLElement>(null);
  const play = now?.play;
  // Where the strip's cover is, for the large one to fly from and back to
  const stripCover = useCallback(() => strip.current?.querySelector(".mini-cover")?.getBoundingClientRect() ?? null, []);
  const close = useCallback(() => setOpen(false), []);
  // Nothing plays any more: the large view closes with the strip
  useEffect(() => {
    if (!play) setOpen(false);
  }, [play]);
  if (!play) return null;
  const playing = now.state === "playing";
  const { time, share } = progress(play);
  return (
    <>
      <footer ref={strip} className={`mini-player${play.mood ? " has-mood" : ""}`} style={moodStyle(play.mood)}
              onClick={() => {
                // Opened once the large cover is decoded, so its first frame is not spent on that
                const image = new Image();
                image.src = imageUrl(play.image);
                image.decode().catch(() => undefined).then(() => setOpen(true));
              }}>
        <div className="mini-progress">
          <div className={`mini-progress-fill${playing ? " moving" : ""}`} style={{ transform: `scaleX(${share})` }} />
        </div>
        <div className="mini-body">
          {/* Keyed by the song, so a new one slides in */}
          <Picture key={play.key} src={play.image} alt={play.name} className="mini-cover" eager />
          <div key={`${play.key}-text`} className="mini-text">
            <span className="mini-title">{play.name}</span>
            <span className="muted">{play.artist}{play.album ? `  ·  ${play.album}` : ""}</span>
          </div>
          <span className="mini-time">{time}</span>
          <span className={playing ? "mini-state playing" : "mini-state"}>
            <Equalizer playing={playing} />
            {stateText(t, playing)}{play.recorded ? t("mini.recorded") : ""}
          </span>
        </div>
      </footer>
      {open && <NowPlayingView now={now} from={stripCover} close={close} openTrack={openTrack} />}
    </>
  );
}
