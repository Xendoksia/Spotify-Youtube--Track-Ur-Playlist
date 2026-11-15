/** Settings (api/settings.py): Spotify and YouTube credentials, language, theme, the automatic check and running in
 * the background, saved together. A changed language or theme builds the window again, as in the Tk window. */

import { createContext, useContext, useEffect, useState } from "react";
import { get, post } from "../api";
import { useDialogs } from "../components/Dialog";
import { useTexts } from "../i18n";

type Tab = "spotify" | "youtube" | "general";

interface Option {
  id: string;
  label: string;
}

interface SettingsData {
  values: Record<string, string>;
  language: string;
  languages: Option[];
  theme: string;
  themes: Option[];
  auto_check: string;
  auto_checks: Option[];
  close_to_tray: boolean;
  autostart: boolean;
  autostart_supported: boolean;
  spotify_steps: string;
}

/** Opens the settings, on a service's tab for its missing credentials */
export const OpenSettingsContext = createContext<(tab?: Tab) => void>(() => {});
export const useOpenSettings = () => useContext(OpenSettingsContext);

function Field({ label, name, secret = false, data, setData }: {
  label: string; name: string; secret?: boolean; data: SettingsData; setData: (data: SettingsData) => void;
}) {
  return (
    <label className="setting-row">
      <span>{label}</span>
      <input className="field" type={secret ? "password" : "text"} spellCheck={false} autoComplete="off"
             value={data.values[name] ?? ""}
             onChange={(event) => setData({ ...data, values: { ...data.values, [name]: event.target.value } })} />
    </label>
  );
}

function Choice({ label, options, value, onChange }: {
  label: string; options: Option[]; value: string; onChange: (value: string) => void;
}) {
  return (
    <label className="setting-row">
      <span>{label}</span>
      <select className="field" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
      </select>
    </label>
  );
}

export default function Settings({ tab, setTab, hidden }: { tab: Tab; setTab: (tab: Tab) => void; hidden: boolean }) {
  const { t } = useTexts();
  const dialogs = useDialogs();
  const [data, setData] = useState<SettingsData | null>(null);
  const [message, setMessage] = useState("");

  // Read anew from the saved settings each time the page is shown
  useEffect(() => {
    if (hidden) return;
    setMessage("");
    get<SettingsData>("/api/settings").then(setData, () => {});
  }, [hidden]);

  if (!data) return null;
  const save = async () => {
    const result = await post<{ ok: boolean; tab?: Tab; title?: string; message?: string; appearance_changed?: boolean }>(
      "/api/settings", data);
    if (!result.ok) {
      setTab(result.tab!);
      await dialogs.alert(result.title!, result.message!);
      return;
    }
    // A new language or theme: the window is built again, back on the settings
    if (result.appearance_changed) {
      location.search = "?section=settings";
      return;
    }
    setMessage(result.message ?? "");
  };

  return (
    <div className="page" hidden={hidden}>
      <header className="toolbar"><h1 className="period-title">{t("settings.title")}</h1></header>
      <nav className="tabs inline">
        {(["spotify", "youtube", "general"] as Tab[]).map((name) => (
          <button key={name} className={tab === name ? "selected" : ""} onClick={() => setTab(name)}>
            {name === "spotify" ? "Spotify" : name === "youtube" ? "YouTube" : t("settings.general")}
          </button>
        ))}
      </nav>
      <section className="card settings-card">
        {tab === "spotify" && (
          <>
            <p className="steps muted">{data.spotify_steps}</p>
            <a className="setting-link" href="https://developer.spotify.com/dashboard" target="_blank" rel="noreferrer">
              {t("settings.open_dashboard")} ↗
            </a>
            <Field label={t("settings.client_id")} name="CLIENT_ID" data={data} setData={setData} />
            <Field label={t("settings.client_secret")} name="CLIENT_SECRET" secret data={data} setData={setData} />
          </>
        )}
        {tab === "youtube" && (
          <>
            <p className="steps muted">{t("settings.youtube_steps")}</p>
            <a className="setting-link" href="https://console.cloud.google.com/apis/library/youtube.googleapis.com"
               target="_blank" rel="noreferrer">
              {t("settings.open_console")} ↗
            </a>
            <Field label={t("settings.api_key")} name="YOUTUBE_API_KEY" secret data={data} setData={setData} />
            <Field label={t("settings.oauth_client_id")} name="YOUTUBE_CLIENT_ID" data={data} setData={setData} />
            <Field label={t("settings.oauth_client_secret")} name="YOUTUBE_CLIENT_SECRET" secret data={data}
                   setData={setData} />
          </>
        )}
        {tab === "general" && (
          <>
            <Choice label={t("settings.language")} options={data.languages} value={data.language}
                    onChange={(language) => setData({ ...data, language })} />
            <Choice label={t("settings.theme")} options={data.themes} value={data.theme}
                    onChange={(theme) => setData({ ...data, theme })} />
            <Choice label={t("settings.auto_check")} options={data.auto_checks} value={data.auto_check}
                    onChange={(value) => setData({ ...data, auto_check: value })} />
            <p className="setting-note muted">{t("settings.auto_check_note")}</p>
            <label className="switch setting-switch">
              <input type="checkbox" checked={data.close_to_tray}
                     onChange={(event) => setData({ ...data, close_to_tray: event.target.checked })} />
              <span className="switch-track"><span className="switch-thumb" /></span>
              {t("settings.close_to_tray")}
            </label>
            <label className={`switch setting-switch${data.autostart_supported ? "" : " disabled"}`}>
              <input type="checkbox" checked={data.autostart} disabled={!data.autostart_supported}
                     onChange={(event) => setData({ ...data, autostart: event.target.checked })} />
              <span className="switch-track"><span className="switch-thumb" /></span>
              {t("settings.autostart")}
            </label>
            <p className="setting-note muted">{t("settings.restart_note")}</p>
          </>
        )}
      </section>
      <div className="settings-footer">
        <span className="muted">{message}</span>
        <button className="button primary" onClick={save}>{t("settings.save")}</button>
      </div>
    </div>
  );
}
