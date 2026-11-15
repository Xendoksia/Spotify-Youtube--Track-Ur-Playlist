/** A strip along the bottom of the window with the song playing in the Spotify app: cover, title, artist, the
 * time into the song with a progress line, and whether the play is recorded yet. A recorded song opens its page. */

import { useTexts } from "../i18n";
import { clock, useNowPlaying } from "../nowPlaying";
import Picture from "./Picture";

export default function MiniPlayer({ openTrack }: { openTrack: (key: string) => void }) {
  const { t } = useTexts();
  const now = useNowPlaying();
  const play = now?.play;
  if (!play) return null;
  const playing = now.state === "playing";
  const { position, duration } = play;
  const time = position !== null && duration ? `${clock(position)} / ${clock(duration)}`
    : position !== null ? clock(position) : "";
  const share = position !== null && duration ? Math.min(1, position / duration) : 0;
  return (
    <footer className={`mini-player${play.recorded ? " clickable" : ""}`}
            onClick={play.recorded ? () => openTrack(play.key) : undefined}>
      <div className="mini-progress">
        <div className={`mini-progress-fill${playing ? " moving" : ""}`} style={{ width: `${share * 100}%` }} />
      </div>
      <div className="mini-body">
        <Picture src={play.image} alt={play.name} className="mini-cover" />
        <div className="mini-text">
          <span className="mini-title">{play.name}</span>
          <span className="muted">{play.artist}{play.album ? `  ·  ${play.album}` : ""}</span>
        </div>
        <span className="mini-time">{time}</span>
        <span className={playing ? "mini-state playing" : "mini-state"}>
          {t(playing ? "mini.playing" : "mini.paused")}{play.recorded ? t("mini.recorded") : ""}
        </span>
      </div>
    </footer>
  );
}
