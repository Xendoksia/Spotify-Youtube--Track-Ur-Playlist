/** A strip along the bottom of the window with the song playing in the Spotify app: cover, title, artist, the
 * time into the song with a progress line, and whether the play is recorded yet, tinted with the cover's color.
 * A click opens the song large (NowPlayingView); from there a recorded song opens its page. */

import { useEffect, useState } from "react";
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

function NowPlayingView({ now, close, openTrack }: {
  now: NowPlaying; close: () => void; openTrack: (key: string) => void;
}) {
  const { t } = useTexts();
  const play = now.play!;
  const playing = now.state === "playing";
  const { share } = progress(play);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);
  return (
    <div className={`now-view${play.mood ? " has-mood" : ""}`} style={moodStyle(play.mood)} onClick={close}>
      <div className="now-view-backdrop" style={{ backgroundImage: `url("${imageUrl(play.image)}")` }} />
      <button className="icon-button now-view-close" onClick={close} aria-label="Esc"><Icon name="close" /></button>
      <div className="now-view-body" onClick={(event) => event.stopPropagation()}>
        <span className="now-view-caption"><Equalizer playing={playing} />{t("mini.now")}</span>
        <Picture key={play.key} src={play.image} alt={play.name} className="now-view-cover" />
        <div key={`${play.key}-text`} className="now-view-text">
          <span className="now-view-title">{play.name}</span>
          <span className="now-view-artist">{play.artist}</span>
          {play.album && <span className="now-view-album">{play.album}</span>}
        </div>
        <div className="now-view-progress">
          <div className="mini-progress">
            <div className={`mini-progress-fill${playing ? " moving" : ""}`} style={{ width: `${share * 100}%` }} />
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
  const play = now?.play;
  // Nothing plays any more: the large view closes with the strip
  useEffect(() => {
    if (!play) setOpen(false);
  }, [play]);
  if (!play) return null;
  const playing = now.state === "playing";
  const { time, share } = progress(play);
  return (
    <>
      <footer className={`mini-player${play.mood ? " has-mood" : ""}`} style={moodStyle(play.mood)}
              onClick={() => setOpen(true)}>
        <div className="mini-progress">
          <div className={`mini-progress-fill${playing ? " moving" : ""}`} style={{ width: `${share * 100}%` }} />
        </div>
        <div className="mini-body">
          {/* Keyed by the song, so a new one slides in */}
          <Picture key={play.key} src={play.image} alt={play.name} className="mini-cover" />
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
      {open && <NowPlayingView now={now} close={() => setOpen(false)} openTrack={openTrack} />}
    </>
  );
}
