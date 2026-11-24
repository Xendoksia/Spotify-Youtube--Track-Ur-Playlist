/** Playlist tracking (api/playlists.py, tracking): one page for Spotify and YouTube. At the top the last check
 * and the tracks added lately, below every change found with filters, and beside them the playlists, to track by
 * link, from the account's own playlists that come in by themselves, or with each one's switch. Network work runs
 * in the backend one task at a time; its progress shows in the top card. */

import { useCallback, useEffect, useRef, useState } from "react";
import { get, imageUrl, post } from "../api";
import { useDialogs } from "../components/Dialog";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import { useTexts } from "../i18n";
import { openSpotify } from "../spotify";
import { useOpenSettings } from "./Settings";

interface Recent {
  title: string; artist: string; service: string; when: string; image: string; uri: string; fresh: boolean;
}

interface Item {
  key: string; service: string; name: string; meta: string; image: string | null; tracked: boolean; url: string;
}

interface Row {
  kind: string; label: string; title: string; artist: string; playlist: string; time: string; image: string | null;
}

interface Tracking {
  hero: { caption: string; title: string; detail: string; recent: Recent[] } | null;
  auto: string;
  busy: string | null;
  status: string;
  login: { service: string; message: string }[];
  tracked_count: number;
  services: { name: string; key: string; logged_in: boolean; has_credentials: boolean }[];
  lists: { found: Item[]; tracked: Item[]; others: Item[] };
  filter: {
    total: string; all: number;
    playlists: { key: string; name: string; image: string | null }[];
    kinds: { event: string; kind: string; label: string; count: number }[];
  };
  days: { date: string; title: string; summary: string; rows: Row[] }[];
}

interface Started {
  started: boolean;
  reason?: "credentials" | "busy" | "error" | "nothing";
  title?: string;
  message?: string;
}

interface Filters { q: string; service: string; playlist: string; event: string }

const NO_FILTERS: Filters = { q: "", service: "", playlist: "", event: "" };
/** How many changes show at first, and how many more each "Show more" adds */
const CHANGES_STEP = 20;
const SERVICE_COLORS: Record<string, string> = { spotify: "#1aa34a", youtube: "#e62117" };

/** A track's page in its service: Spotify through the app, a YouTube video in the browser */
function trackLink(track: Recent): { href: string; onClick?: ReturnType<typeof openSpotify> } {
  if (track.service === "youtube") return { href: `https://www.youtube.com/watch?v=${encodeURIComponent(track.uri)}` };
  return {
    href: `https://open.spotify.com/search/${encodeURIComponent(`${track.title} ${track.artist}`)}`,
    onClick: openSpotify(track.artist, track.title),
  };
}

function Hero({ data, busy, status, onCheck, onLogin }: {
  data: Tracking; busy: boolean; status: string; onCheck: () => void; onLogin: (service: string) => void;
}) {
  const { t } = useTexts();
  const hero = data.hero;
  const login = data.login[0];
  const backdrop = hero?.recent[0]?.image;
  let caption = hero?.caption ?? "";
  let title = hero?.title ?? t("track.hero.first");
  let detail = hero?.detail ?? t("track.hero.first_text");
  let tone = "";
  if (busy) {
    caption = t("track.hero.checking");
    detail = status;
    tone = " checking";
  } else if (login) {
    caption = t("track.hero.login");
    title = login.message.split("\n")[0];
    detail = "";
    tone = " login";
  }
  return (
    <section className="hero trk-hero" aria-label={caption}>
      {backdrop && <div className="hero-backdrop" style={{ backgroundImage: `url("${imageUrl(backdrop)}")` }} />}
      <div className="trk-hero-body">
        <div className="trk-hero-head">
          <div className="trk-hero-text">
            <span className={`hero-caption${tone}`}>{caption}</span>
            <span className="trk-hero-title">{title}</span>
            {detail && <span className="hero-detail">{detail}</span>}
            {busy && <span className="trk-progress" aria-hidden="true"><span /></span>}
          </div>
          <div className="trk-hero-actions">
            {login && !busy ? (
              <button className="button accent spotify" onClick={() => onLogin(login.service)}>
                {t("track.hero.login_button", { service: login.service })}
              </button>
            ) : (
              <button className="button accent spotify" disabled={busy || !data.tracked_count} onClick={onCheck}>
                {t("track.hero.check", { count: data.tracked_count })}
              </button>
            )}
            <span className="trk-auto"><span className="trk-dot" />{data.auto}</span>
          </div>
        </div>
        {hero && hero.recent.length > 0 && (
          <ul className="trk-recent" aria-label={t("track.recent")}>
            {hero.recent.map((track) => {
              const link = trackLink(track);
              return (
                <li key={`${track.title}|${track.artist}`}>
                  <a className="trk-cover" href={link.href} target="_blank" rel="noreferrer" onClick={link.onClick}
                     title={t("track.open", { service: track.service === "youtube" ? "YouTube" : "Spotify" })}>
                    <span className={`trk-cover-art${track.fresh ? " fresh" : ""}`}>
                      <Picture src={track.image} alt={track.title} />
                      {track.fresh && <span className="trk-new">{t("track.recent.new")}</span>}
                    </span>
                    <span className="trk-cover-title">{track.title}</span>
                    <span className="trk-cover-meta">{track.artist}</span>
                    <span className="trk-cover-meta">{track.when}</span>
                  </a>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

function FilterBar({ data, filters, setFilters }: {
  data: Tracking; filters: Filters; setFilters: (change: Partial<Filters>) => void;
}) {
  const { t, number } = useTexts();
  const [text, setText] = useState(filters.q);
  // The search is asked for once typing pauses
  useEffect(() => {
    const timer = setTimeout(() => setFilters({ q: text }), 200);
    return () => clearTimeout(timer);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  const playlist = data.filter.playlists.find((p) => p.key === filters.playlist);
  return (
    <div className="card trk-filter" role="search">
      <div className="trk-filter-row">
        <label className="trk-search">
          <Icon name="search" />
          <span className="trk-hidden">{t("track.search")}</span>
          <input value={text} placeholder={t("track.search")} onChange={(event) => setText(event.target.value)} />
          {text && <button className="trk-clear" aria-label={t("track.clear")} onClick={() => setText("")}>✕</button>}
        </label>
        <div className="segmented trk-segmented" role="tablist">
          {[{ key: "", name: t("track.service_all") }, ...data.services].map((service) => (
            <button key={service.key} role="tab" aria-selected={filters.service === service.key}
                    className={filters.service === service.key ? "selected" : ""}
                    onClick={() => setFilters({ service: service.key, playlist: "" })}>
              {service.key && <span className="trk-dot" style={{ background: SERVICE_COLORS[service.key] }} />}
              {service.name}
            </button>
          ))}
        </div>
        <label className={`trk-pick${playlist ? " selected" : ""}`}>
          {playlist?.image ? <Picture src={playlist.image} alt={playlist.name} round /> : <span className="trk-pick-icon"><Icon name="list" /></span>}
          <span className="trk-pick-name">{playlist?.name ?? t("track.playlist_all")}</span>
          <select value={filters.playlist} aria-label={t("column.playlist")}
                  onChange={(event) => setFilters({ playlist: event.target.value })}>
            <option value="">{t("track.playlist_all")}</option>
            {data.filter.playlists.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
          </select>
        </label>
      </div>
      <div className="trk-kinds">
        <button className={`trk-kind${!filters.event ? " selected" : ""}`} aria-pressed={!filters.event}
                onClick={() => setFilters({ event: "" })}>
          {t("track.kind_all")} <span className="trk-count">{number(data.filter.all)}</span>
        </button>
        {data.filter.kinds.map((kind) => (
          <button key={kind.event} className={`trk-kind${filters.event === kind.event ? " selected" : ""}`}
                  aria-pressed={filters.event === kind.event} disabled={!kind.count && filters.event !== kind.event}
                  onClick={() => setFilters({ event: filters.event === kind.event ? "" : kind.event })}>
            <span className={`trk-dot event-dot-${kind.kind}`} />{kind.label}
            <span className="trk-count">{number(kind.count)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Switch({ on, label, onChange }: { on: boolean; label: string; onChange: () => void }) {
  return <button className="trk-switch" role="switch" aria-checked={on} aria-label={label} onClick={onChange} />;
}

function ListRow({ item, checking, onToggle }: { item: Item; checking: boolean; onToggle: () => void }) {
  const { t } = useTexts();
  return (
    <div className={`trk-list-row${item.tracked ? "" : " off"}`}>
      {item.image ? <Picture src={item.image} alt={item.name} className="trk-list-pic" />
        : <span className="picture placeholder trk-list-pic">{item.name.trim().charAt(0).toUpperCase()}</span>}
      <span className="trk-list-text">
        <a className="trk-list-name" href={item.url} target="_blank" rel="noreferrer">{item.name}</a>
        <span className={`trk-list-meta${checking ? " checking" : ""}`}>
          <span className="trk-dot" style={{ background: SERVICE_COLORS[item.service] }} />
          {checking ? `${t("track.hero.checking")}…` : item.meta}
        </span>
      </span>
      <Switch on={item.tracked} label={t("track.toggle", { name: item.name })} onChange={onToggle} />
    </div>
  );
}

function Lists({ data, busy, checking, start, change }: {
  data: Tracking; busy: boolean; checking: string | null;
  start: (route: string, body?: object) => Promise<boolean>; change: (body: Promise<Tracking>) => void;
}) {
  const { t } = useTexts();
  const [link, setLink] = useState("");
  const { found, tracked, others } = data.lists;
  const count = found.length + tracked.length + others.length;
  const toggle = (item: Item) => change(post<Tracking>("/api/tracking/track", { key: item.key, tracked: !item.tracked }));
  const loggedIn = data.services.filter((service) => service.logged_in);
  return (
    <aside className="card trk-lists" aria-labelledby="trk-lists-title">
      <div className="trk-lists-head">
        <h2 id="trk-lists-title" className="card-title">{t("track.lists")}</h2>
        <span className="muted">{t("track.lists.count", { count, tracked: tracked.length })}</span>
      </div>

      <form className="trk-link" onSubmit={async (event) => {
        event.preventDefault();
        if (link.trim() && await start("/api/tracking/add", { link })) setLink("");
      }}>
        <label htmlFor="trk-link" className="muted">{t("track.link.label")}</label>
        <div className="trk-link-field">
          <Icon name="link" />
          <input id="trk-link" value={link} placeholder={t("track.link.placeholder")}
                 onChange={(event) => setLink(event.target.value)} />
          <button className="button accent spotify" disabled={busy || !link.trim()}>{t("track.link.add")}</button>
        </div>
        {loggedIn.length > 0 ? (
          <span className="muted trk-small">
            {t("track.found.auto")} · <button type="button" className="trk-text-button" disabled={busy}
                                              onClick={() => post("/api/tracking/find", {})}>{t("track.found.refresh")}</button>
          </span>
        ) : (
          <div className="trk-connect">
            <strong>{t("track.connect.title")}</strong>
            <span className="muted">{t("track.connect.text")}</span>
            <div className="trk-connect-buttons">
              {data.services.map((service) => (
                <button key={service.key} type="button" className={`button${service.key === "spotify" ? " accent spotify" : ""}`}
                        disabled={busy} onClick={() => start("/api/playlists/login", { service: service.name })}>
                  {t("login.button", { account: service.key === "youtube" ? "Google" : service.name })}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>

      {found.length > 0 && (
        <div className="trk-found">
          <div className="trk-found-head">
            <span className="hero-caption">{t("track.found.title", { count: found.length })}</span>
            {found.length > 1 && (
              <>
                <button className="trk-text-button" onClick={() => change(post<Tracking>("/api/tracking/track-found", {}))}>
                  {t("track.found.track_all")}
                </button>
                <button className="trk-text-button muted" onClick={() => change(post<Tracking>("/api/tracking/skip", { keys: found.map((item) => item.key) }))}>
                  {t("track.found.skip_all")}
                </button>
              </>
            )}
          </div>
          {found.map((item) => (
            <div key={item.key} className="trk-found-item">
              <div className="trk-list-row">
                {item.image ? <Picture src={item.image} alt={item.name} className="trk-list-pic" />
                  : <span className="picture placeholder trk-list-pic">{item.name.trim().charAt(0).toUpperCase()}</span>}
                <span className="trk-list-text">
                  <strong className="trk-list-name">{item.name}</strong>
                  <span className="trk-list-meta">
                    <span className="trk-dot" style={{ background: SERVICE_COLORS[item.service] }} />{item.meta}
                  </span>
                </span>
              </div>
              <div className="trk-found-buttons">
                <button className="button accent spotify" onClick={() => toggle(item)}>{t("track.found.track")}</button>
                <button className="button" onClick={() => change(post<Tracking>("/api/tracking/skip", { keys: [item.key] }))}>
                  {t("track.found.skip")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tracked.length > 0 && (
        <div className="trk-group">
          <span className="hero-caption">{t("track.tracked", { count: tracked.length })}</span>
          {tracked.map((item) => (
            <ListRow key={item.key} item={item} checking={busy && checking === item.key} onToggle={() => toggle(item)} />
          ))}
        </div>
      )}
      {others.length > 0 && (
        <div className="trk-group divided">
          <span className="hero-caption">{t("track.others", { count: others.length })}</span>
          {others.map((item) => <ListRow key={item.key} item={item} checking={false} onToggle={() => toggle(item)} />)}
        </div>
      )}
    </aside>
  );
}

export default function Playlists() {
  const { t } = useTexts();
  const dialogs = useDialogs();
  const openSettings = useOpenSettings();
  const [data, setData] = useState<Tracking | null>(null);
  const [filters, setFilterState] = useState<Filters>(NO_FILTERS);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [checking, setChecking] = useState<string | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const [shown, setShown] = useState(CHANGES_STEP);
  useEffect(() => setShown(CHANGES_STEP), [filters]);

  const load = useCallback(() => {
    const f = filtersRef.current;
    get<Tracking>("/api/tracking", { q: f.q, service: f.service, playlist: f.playlist, event: f.event }).then((result) => {
      setData(result);
      setBusy(result.busy !== null);
      setStatus(result.status);
    }, () => {});
  }, []);
  useEffect(load, [load, filters]);

  const setFilters = useCallback((change: Partial<Filters>) => {
    setFilterState((current) => {
      const next = { ...current, ...change };
      return Object.keys(change).every((key) => current[key as keyof Filters] === next[key as keyof Filters])
        ? current : next;
    });
  }, []);

  const start = useCallback(async (route: string, body: object = {}) => {
    const result = await post<Started>(route, body);
    if (result.started || result.reason === "busy") return result.started;
    if (result.reason === "credentials") {
      openSettings(String((body as { service?: string }).service ?? "spotify").toLowerCase() as "spotify" | "youtube");
    } else if (result.reason === "nothing") {
      await dialogs.alert(result.title!, result.message!);
    } else if (result.reason === "error") {
      await dialogs.alert(t("dialog.error"), result.message!);
    }
    return false;
  }, [dialogs, t, openSettings]);

  // The list changes (a check, the automatic one, another device, playlists found in the account) and the task's
  // progress and end
  useEffect(() => window.tracker.onEvent(async (message) => {
    if (message.event === "playlists" || (message.event === "synced" && (message.playlists || message.events))) {
      load();
    }
    if (message.event !== "task") return;
    if (typeof message.status === "string") setStatus(message.status);
    setBusy(Boolean(message.busy));
    setChecking(typeof message.checking === "string" ? message.checking : null);
    if (message.state === "error") await dialogs.alert(t("dialog.error"), String(message.message));
    if (message.state === "login" && message.service
        && await dialogs.confirm(t("dialog.login_required"), String(message.message))) {
      start("/api/playlists/login", { service: message.service });
    }
  }), [load, dialogs, start, t]);
  // The pointer waits while a task runs
  useEffect(() => {
    document.body.classList.toggle("working", busy);
  }, [busy]);

  if (!data) return null;
  const change = (body: Promise<Tracking>) => body.then((result) => {
    setData(result);
    load();
  }, () => {});
  const filtered = filters.q || filters.service || filters.playlist || filters.event;
  // The first `shown` changes, cut inside the day they end in
  const total = data.days.reduce((sum, day) => sum + day.rows.length, 0);
  let left = shown;
  const days = data.days.flatMap((day) => {
    if (left <= 0) return [];
    const rows = day.rows.slice(0, left);
    left -= rows.length;
    return [{ ...day, rows }];
  });

  return (
    <div className="page">
      <div className="overview">
        <Hero data={data} busy={busy} status={status} onCheck={() => start("/api/tracking/check")}
              onLogin={(service) => start("/api/playlists/login", { service })} />
        <div className="trk-columns">
          <section className="trk-changes" aria-labelledby="trk-changes-title">
            <div className="trk-changes-head">
              <h2 id="trk-changes-title">{t("track.changes")}</h2>
              <span className="muted">{data.filter.total}</span>
            </div>
            <FilterBar data={data} filters={filters} setFilters={setFilters} />
            {data.days.length === 0 && (
              <div className="card trk-empty">
                <strong>{filtered ? t("track.no_results") : t("track.empty")}</strong>
                {filtered && <button className="trk-text-button" onClick={() => setFilterState(NO_FILTERS)}>{t("track.clear")}</button>}
              </div>
            )}
            {days.map((day) => (
              <div key={day.date} className="card trk-day">
                <div className="trk-day-head"><strong>{day.title}</strong><span className="muted">{day.summary}</span></div>
                {day.rows.map((row, index) => (
                  <div key={index} className="trk-row">
                    <span className={`event-badge event-${row.kind}`}>{row.label}</span>
                    {row.image ? <Picture src={row.image} alt={row.title} className="trk-row-pic" />
                      : <span className="picture placeholder trk-row-pic">{row.title.trim().charAt(0)}</span>}
                    <span className="trk-row-text">
                      <span className="trk-row-title">{row.title}</span>
                      {row.artist && <span className="muted trk-row-artist">{row.artist}</span>}
                    </span>
                    <span className="trk-chip">{row.playlist}</span>
                    <span className="muted trk-row-time">{row.time}</span>
                  </div>
                ))}
              </div>
            ))}
            {total > shown && (
              <button className="button trk-more" onClick={() => setShown(shown + CHANGES_STEP)}>
                {t("track.more", { count: total - shown })}
              </button>
            )}
          </section>
          <Lists data={data} busy={busy} checking={checking} start={start} change={change} />
        </div>
      </div>
    </div>
  );
}
