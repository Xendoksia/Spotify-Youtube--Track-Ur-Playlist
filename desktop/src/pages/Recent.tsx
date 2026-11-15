/** The Recently played tab: recording on or off, the song Spotify plays now, and the last plays grouped by day,
 * each opening its song's page (api/listening.py). The list has no covers, as in the Tk window. */

import { useCallback, useEffect, useState } from "react";
import { get, post } from "../api";
import Picture from "../components/Picture";
import { useTexts } from "../i18n";
import { useOpenDetail } from "../navigation";
import { useNowPlaying } from "../nowPlaying";

interface RecentData {
  info: string;
  empty: string;
  days: {
    date: string;
    title: string;
    summary: string;
    plays: { id: number; key: string; time: string; title: string; subtitle: string; length: string }[];
  }[];
}

function NowCard() {
  const { t } = useTexts();
  const open = useOpenDetail()!;
  const now = useNowPlaying();
  if (!now) return null;
  const play = now.play;
  if (!play) {
    const message = !now.available || now.state === "off" ? t("listening.now.off")
      : now.error ? t("listening.now.error", { error: now.error }) : t("listening.now.idle");
    return <section className={`card now-card${now.error ? " error" : ""}`}>{message}</section>;
  }
  const playing = now.state === "playing";
  let state = t(playing ? "listening.card.playing" : "listening.card.paused", { listened: play.listened });
  if (play.recorded) state += t("listening.now.recorded");
  return (
    <section className={`card now-card${play.recorded ? " clickable" : ""}`}
             onClick={play.recorded ? () => open("track_key", play.key) : undefined}>
      <Picture src={play.image} alt={play.name} className="now-cover" />
      <div className="now-text">
        <span className="now-title">{play.name}</span>
        <span className="muted">{[play.artist, play.album].filter(Boolean).join("  ·  ")}</span>
        <span className={playing ? "now-state playing" : "now-state"}>{state}</span>
      </div>
    </section>
  );
}

export default function Recent({ hidden }: { hidden: boolean }) {
  const { t } = useTexts();
  const open = useOpenDetail()!;
  const now = useNowPlaying();
  const [data, setData] = useState<RecentData | null>(null);
  // Set at once on a click, before the next ask for what plays tells the backend's answer
  const [recording, setRecording] = useState<boolean | null>(null);

  const load = useCallback(() => {
    get<RecentData>("/api/recent").then(setData, () => {});
  }, []);
  useEffect(load, [load]);
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event === "plays" || message.event === "synced") load();
    if (message.event === "recording") setRecording(null);
  }), [load]);

  const enabled = recording ?? now?.enabled ?? false;
  const toggle = async () => {
    setRecording(!enabled);
    try {
      await post("/api/recording", { enabled: !enabled });
    } finally {
      setRecording(null);
    }
  };

  return (
    <div className="page" hidden={hidden}>
      <div className="overview">
        <div className="recent-toolbar">
          <label className={`switch${now?.available ? "" : " disabled"}`}>
            <input type="checkbox" checked={enabled} disabled={!now?.available} onChange={toggle} />
            <span className="switch-track"><span className="switch-thumb" /></span>
            {t("listening.track_toggle")}
          </label>
          <span className="spacer" />
          <span className="muted">{data?.info}</span>
        </div>
        <NowCard />
        {data && data.days.length === 0 && <p className="empty">{data.empty}</p>}
        {data?.days.map((day) => (
          <section key={day.date} className="recent-day">
            <header className="recent-day-header">
              <h2>{day.title}</h2>
              <span className="muted">{day.summary}</span>
            </header>
            <ol className="recent-list">
              {day.plays.map((play) => (
                <li key={play.id} className="recent-row clickable" title={`${play.title}\n${play.subtitle}`}
                    onClick={() => open("track_key", play.key)}>
                  <span className="recent-time">{play.time}</span>
                  <div className="recent-text">
                    <span className="recent-title">{play.title}</span>
                    <span className="muted">{play.subtitle}</span>
                  </div>
                  <span className="recent-length">{play.length}</span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
