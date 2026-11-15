/** Every change recorded in one service's playlists, filterable by playlist and event, and saved as CSV. */

import { useCallback, useEffect, useState } from "react";
import { get, post } from "../api";
import { useTexts } from "../i18n";

interface HistoryData {
  playlists: { id: string; name: string }[];
  events: { id: string; label: string }[];
  rows: { kind: string; label: string; checked: string; playlist: string; track: string; added: string }[];
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
        <div className="history-filters">
          <label>{t("history.source")}
            <select className="field" value={service} onChange={(change) => {
              setService(change.target.value);
              setPlaylist("");
            }}>
              {services.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
            </select>
          </label>
          <label>{t("history.playlist")}
            <select className="field wide" value={playlist} onChange={(change) => setPlaylist(change.target.value)}>
              <option value="">{t("history.all")}</option>
              {data?.playlists.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>{t("history.event")}
            <select className="field" value={event} onChange={(change) => setEvent(change.target.value)}>
              <option value="">{t("history.all")}</option>
              {data?.events.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <span className="spacer" />
          <button className="button" onClick={load}>{t("history.refresh")}</button>
          <button className="button" onClick={exportCsv}>{t("history.export")}</button>
        </div>
        <div className="table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th>{t("history.detected")}</th>
                <th>{t("column.playlist")}</th>
                <th>{t("history.event_column")}</th>
                <th>{t("history.item")}</th>
                <th>{t("history.added")}</th>
              </tr>
            </thead>
            <tbody>
              {data?.rows.map((row, index) => (
                <tr key={index}>
                  <td className="nowrap muted">{row.checked}</td>
                  <td>{row.playlist}</td>
                  <td className="nowrap"><span className={`event-badge event-${row.kind}`}>{row.label}</span></td>
                  <td className="track-cell">{row.track}</td>
                  <td className="nowrap muted">{row.added}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">{t("history.note")}</p>
      </div>
    </div>
  );
}
