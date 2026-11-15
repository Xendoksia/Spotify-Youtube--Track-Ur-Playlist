import { useEffect, useMemo, useState } from "react";
import { get } from "./api";
import Icon, { IconName } from "./components/Icon";
import { AppInfo, makeTexts, TextsContext } from "./i18n";
import Overview from "./pages/Overview";

type Section = "listening" | "playlists" | "account" | "settings" | "help";

// The sections of the Tk window's sidebar; only the statistics are moved over so far
const SECTIONS: { name: Section; label: string; icon: IconName; ready: boolean }[] = [
  { name: "listening", label: "nav.listening", icon: "music", ready: true },
  { name: "playlists", label: "nav.playlists", icon: "list", ready: false },
  { name: "account", label: "nav.account", icon: "account", ready: false },
  { name: "help", label: "nav.help", icon: "help", ready: false },
  { name: "settings", label: "settings.title", icon: "settings", ready: false },
];

export default function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("listening");

  useEffect(() => {
    get<AppInfo>("/api/app").then(setInfo, (reason) => setError(String(reason)));
  }, []);

  useEffect(() => {
    if (info && info.theme !== "system") document.documentElement.dataset.theme = info.theme;
    else delete document.documentElement.dataset.theme;
    if (info) document.documentElement.lang = info.language;
  }, [info]);

  const texts = useMemo(() => (info ? makeTexts(info) : null), [info]);
  if (error) return <div className="splash">{error}</div>;
  if (!texts) return <div className="splash" />;
  const { t } = texts;

  return (
    <TextsContext.Provider value={texts}>
      <div className="shell">
        <nav className="sidebar">
          <div className="brand">
            <span className="brand-mark"><Icon name="music" /></span>
            {t("app.title")}
          </div>
          {SECTIONS.map((item) => (
            <button
              key={item.name}
              className={`nav-item${section === item.name ? " selected" : ""}`}
              disabled={!item.ready}
              onClick={() => setSection(item.name)}
            >
              <Icon name={item.icon} />
              <span>{t(item.label)}</span>
            </button>
          ))}
        </nav>
        <main className="content">{section === "listening" && <Overview />}</main>
      </div>
    </TextsContext.Provider>
  );
}
