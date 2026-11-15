/** Playlist tracking (api/playlists.py): a tab for each service with its playlists as cards, and the history of
 * the changes found. Network work runs in the backend one task at a time; its progress shows as a status line. */

import { useCallback, useEffect, useState } from "react";
import { get, post } from "../api";
import { useDialogs } from "../components/Dialog";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import { useTexts } from "../i18n";
import History from "./History";
import { useOpenSettings } from "./Settings";

interface EventText {
  kind: "added" | "removed" | "unplayable" | "playable" | "initial";
  label: string;
}

interface Card {
  id: string;
  name: string;
  tracked: boolean;
  details: string;
  checked: string;
  last_change: string;
  changes: (EventText & { symbol: string; count: string })[];
  url: string;
  /** The newest tracks' covers (or video thumbnails), one per album, newest first */
  covers: string[];
  latest: string;
}

/** A playlist's picture made of its newest covers: four in a square, else the newest alone. */
function Covers({ covers, name, tracked }: { covers: string[]; name: string; tracked: boolean }) {
  const shown = covers.length >= 4 ? covers.slice(0, 4) : covers.slice(0, 1);
  return (
    <div className={`playlist-cover${shown.length === 4 ? " mosaic" : ""}`}>
      {shown.length ? shown.map((src) => <Picture key={src} src={src} alt={name} />)
        : <span className="picture placeholder">{name.trim().charAt(0).toUpperCase()}</span>}
      <span className="check-mark">{tracked && <Icon name="check" />}</span>
    </div>
  );
}

interface Result {
  playlists: { name: string; meta: string; note: string; error: boolean;
               rows: (EventText & { track: string; date: string })[] }[];
}

interface Page {
  name: string;
  key: string;
  login: { user: string | null; text: string; button: string };
  has_credentials: boolean;
  playlists: Card[];
  tracked_count: number;
  result: Result | null;
  busy: string | null;
}

interface Started {
  started: boolean;
  reason?: "credentials" | "busy" | "error" | "nothing";
  title?: string;
  message?: string;
}

interface Services {
  services: { name: string; key: string }[];
  busy: string | null;
  status: string;
}

function ServicePanel({ name, busy, hidden }: { name: string; busy: boolean; hidden: boolean }) {
  const { t } = useTexts();
  const dialogs = useDialogs();
  const openSettings = useOpenSettings();
  const [page, setPage] = useState<Page | null>(null);
  const [link, setLink] = useState("");

  const load = useCallback(() => {
    get<Page>("/api/playlists", { service: name }).then(setPage, () => {});
  }, [name]);
  useEffect(load, [load]);

  const start = useCallback(async (action: string, body: object = {}) => {
    const result = await post<Started>(`/api/playlists/${action}`, { service: name, ...body });
    if (result.started || result.reason === "busy") return result.started;
    if (result.reason === "credentials") {
      // Without the service's API details its settings tab opens, as in the Tk window
      openSettings(name.toLowerCase() as "spotify" | "youtube");
    } else if (result.reason === "nothing") {
      await dialogs.alert(result.title!, result.message!);
    } else if (result.reason === "error") {
      await dialogs.alert(t("dialog.error"), result.message!);
    }
    return false;
  }, [name, dialogs, t, openSettings]);

  useEffect(() => window.tracker.onEvent(async (message) => {
    if (message.event === "playlists" && message.service === name) load();
    if (message.event === "synced" && (message.playlists || message.events)) load();
    // The end of this service's task: a failure is said, and logging in again is offered
    if (message.event === "task" && message.service === name) {
      if (message.state === "error") await dialogs.alert(t("dialog.error"), String(message.message));
      if (message.state === "login" && await dialogs.confirm(t("dialog.login_required"), String(message.message))) {
        start("login");
      }
    }
  }), [name, load, dialogs, start, t]);

  if (!page) return null;
  const change = (body: Promise<Page>) => body.then(setPage, () => {});

  return (
    <div className="page" hidden={hidden}>
      <div className="overview">
        <div className="panel-top">
          <button className="button" disabled={busy} onClick={() => start("load")}>
            {t("panel.load_playlists", { service: name })}
          </button>
          <span className="spacer" />
          {page.login.text && <span className="login-text">{page.login.text}</span>}
          <button className="button" disabled={busy} onClick={() => start("login")}>{page.login.button}</button>
        </div>
        <form className="link-row" onSubmit={async (event) => {
          event.preventDefault();
          if (link.trim() && await start("add", { link })) setLink("");
        }}>
          <label htmlFor={`link-${name}`}>{t("panel.or_link")}</label>
          <input id={`link-${name}`} className="field" value={link} onChange={(event) => setLink(event.target.value)} />
          <button className="button" disabled={busy}>{t("panel.add")}</button>
        </form>
        <p className="muted">{t("panel.hint")}</p>

        {page.playlists.length === 0 && <p className="empty">{t("panel.empty", { service: name })}</p>}
        <div className="playlist-grid">
          {page.playlists.map((card) => (
            <div key={card.id} role="checkbox" aria-checked={card.tracked} tabIndex={0}
                 className={`playlist-card${card.tracked ? ` tracked ${page.key}` : ""}`}
                 onClick={() => change(post<Page>("/api/playlists/toggle", { service: name, id: card.id }))}
                 onKeyDown={(event) => {
                   if (event.key === " " || event.key === "Enter") {
                     event.preventDefault();
                     change(post<Page>("/api/playlists/toggle", { service: name, id: card.id }));
                   }
                 }}>
              <Covers covers={card.covers} name={card.name} tracked={card.tracked} />
              <div className="playlist-body">
                <div className="playlist-head">
                  <span className="playlist-name">{card.name}</span>
                  <a className="playlist-open" href={card.url} target="_blank" rel="noreferrer"
                     onClick={(event) => event.stopPropagation()}>
                    {t("panel.open")} ↗
                  </a>
                </div>
                {card.details && <span className="muted">{card.details}</span>}
                <span className="muted">{card.checked}</span>
                {card.latest && <span className="playlist-latest" title={card.latest}>{card.latest}</span>}
                {card.changes.length > 0 && (
                  <span className="playlist-changes">
                    <span className="muted">{card.last_change}</span>
                    {card.changes.map((item) => (
                      <span key={item.kind} className={`event-${item.kind}`} title={item.label}>
                        {item.symbol}{item.count}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="panel-footer">
          <button className="button" onClick={() => change(post<Page>("/api/playlists/all", { service: name, tracked: true }))}>
            {t("panel.select_all")}
          </button>
          <button className="button" onClick={() => change(post<Page>("/api/playlists/all", { service: name, tracked: false }))}>
            {t("panel.clear_selection")}
          </button>
          <span className="spacer" />
          <button className={`button accent ${page.key}`} disabled={busy} onClick={() => start("check")}>
            {t("panel.check", { count: page.tracked_count })}
          </button>
        </div>

        {page.result && (
          <section className="card">
            <h2 className="card-title"><Icon name="history" />{t("panel.last_result")}</h2>
            {page.result.playlists.map((playlist, index) => (
              <div key={index} className="result-playlist">
                <div className="result-head">
                  <strong>{playlist.name}</strong>
                  {playlist.meta && <span className="muted">{playlist.meta}  ·  </span>}
                  <span className={playlist.error ? "event-removed" : "muted"}>{playlist.note}</span>
                </div>
                {playlist.rows.map((row, rowIndex) => (
                  <div key={rowIndex} className="result-row">
                    <span className={`event-badge event-${row.kind}`}>{row.label}</span>
                    <span>{row.track}</span>
                    {row.date && <span className="muted">{row.date}</span>}
                  </div>
                ))}
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

export default function Playlists() {
  const { t } = useTexts();
  const [services, setServices] = useState<Services | null>(null);
  const [tab, setTab] = useState("Spotify");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<Services>("/api/services").then((result) => {
      setServices(result);
      setStatus(result.status);
      setBusy(result.busy !== null);
    }, () => {});
  }, []);
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event !== "task") return;
    if (typeof message.status === "string") setStatus(message.status);
    setBusy(Boolean(message.busy));
  }), []);
  // The pointer waits while a task runs, as in the Tk window
  useEffect(() => {
    document.body.classList.toggle("working", busy);
  }, [busy]);

  if (!services) return null;
  const tabs = [...services.services.map((service) => service.name), "history"];
  return (
    <>
      <nav className="tabs">
        {tabs.map((name) => (
          <button key={name} className={tab === name ? "selected" : ""} onClick={() => setTab(name)}>
            {name === "history" ? t("tab.history") : name}
          </button>
        ))}
        <span className="spacer" />
        <span className="status-line" title={status}>{status}</span>
      </nav>
      {services.services.map((service) => (
        <ServicePanel key={service.name} name={service.name} busy={busy} hidden={tab !== service.name} />
      ))}
      <History hidden={tab !== "history"} services={services.services} />
    </>
  );
}
