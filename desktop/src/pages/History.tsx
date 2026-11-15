/** Every change recorded in one service's playlists, filterable by playlist and event, and saved as CSV. */

import { useCallback, useEffect, useState } from "react";
import { get, post } from "../api";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import { useTexts } from "../i18n";

interface Row {
  kind: string;
  label: string;
  time: string;
  playlist: string;
  title: string;
  artist: string;
  added: string;
  image: string | null;
}

interface Day {
  date: string;
  title: string;
  counts: { kind: string; label: string; symbol: string; count: string }[];
  rows: Row[];
}

interface HistoryData {
  playlists: { id: string; name: string }[];
  events: { id: string; label: string }[];
  days: Day[];
}

export default function History({ hidden, services }: { hidden: boolean; services: { name: string; key: string }[] }) {
  const { t } = useTexts();
  const [service, setService] = useState(services[0]?.name ?? "Spotify");
  const [playlist, setPlaylist] = useState("");
  const [event, setEvent] = useState("");
  const [data, setData] = useState<HistoryData | null>(null);

  const load = useCallback(() => {
    get<HistoryData>("/api/history", { service, playlist, event }).then(setData, () => {});
  }, [service, playlist, event]);
  useEffect(load, [load]);
  // A check here, the automatic one or one on another device found changes
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event === "playlists" || (message.event === "synced" && (message.events || message.playlists))) load();
  }), [load]);

  const exportCsv = async () => {
    const key = services.find((item) => item.name === service)?.key ?? service.toLowerCase();
    const path = await window.tracker.savePath(`${key}_history.csv`, t("csv.filetype"));
    if (path) await post("/api/history/export", { service, path });
  };

  return (
    <div className="page" hidden={hidden}>
      <div className="overview">
        <section className="history-filters">
          <div className="segmented" role="tablist">
            {services.map((item) => (
              <button key={item.name} role="tab" aria-selected={service === item.name}
                      className={service === item.name ? "selected" : ""}
                      onClick={() => {
                        setService(item.name);
                        setPlaylist("");
                      }}>
                {item.name}
              </button>
            ))}
          </div>
          <select className="field wide" aria-label={t("history.playlist")} value={playlist}
                  onChange={(change) => setPlaylist(change.target.value)}>
            <option value="">{t("history.playlist")} {t("history.all")}</option>
            {data?.playlists.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className="field" aria-label={t("history.event")} value={event}
                  onChange={(change) => setEvent(change.target.value)}>
            <option value="">{t("history.event")} {t("history.all")}</option>
            {data?.events.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
          <span className="spacer" />
          <button className="button" onClick={load}><Icon name="sync" />{t("history.refresh")}</button>
          <button className="button" onClick={exportCsv}><Icon name="download" />{t("history.export")}</button>
        </section>

        {data && data.days.length === 0 && <p className="empty">{t("stats.empty")}</p>}
        {data?.days.map((day) => (
          <section key={day.date} className="history-day">
            <header className="history-day-head">
              <h2>{day.title}</h2>
              {day.counts.map((count) => (
                <span key={count.kind} className={`event-badge event-${count.kind}`} title={count.label}>
                  {count.symbol}{count.count}
                </span>
              ))}
            </header>
            <ul className="history-rows">
              {day.rows.map((row, index) => (
                <li key={index} className={`history-row event-row-${row.kind}`}>
                  <span className="history-time">{row.time}</span>
                  {row.image ? <Picture src={row.image} alt={row.title} className="history-picture" />
                    : <span className="picture placeholder history-picture"><Icon name="list" /></span>}
                  <div className="history-text">
                    <span className="history-title">{row.title}</span>
                    <span className="history-subtitle">
                      {[row.artist, row.playlist].filter(Boolean).join("  ·  ")}
                    </span>
                  </div>
                  <span className="history-added">{row.added}</span>
                  <span className={`event-badge event-${row.kind}`}>{row.label}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <p className="muted small">{t("history.note")}</p>
      </div>
    </div>
  );
}
