import { useEffect, useMemo, useState } from "react";
import { get } from "./api";
import Icon, { IconName } from "./components/Icon";
import { AppInfo, makeTexts, TextsContext } from "./i18n";
import MiniPlayer from "./components/MiniPlayer";
import { NowPlayingContext, useNowPlayingPoll } from "./nowPlaying";
import Listening, { OpenRequest } from "./pages/Listening";

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
  const [request, setRequest] = useState<OpenRequest | null>(null);
  const now = useNowPlayingPoll();
  // The mini player's song opens in the Listening section, from any section
  const openTrack = (key: string) => {
    setSection("listening");
    setRequest((before) => ({ column: "track_key", key, n: (before?.n ?? 0) + 1 }));
  };

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
      <NowPlayingContext.Provider value={now}>
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
        <main className="main">
          <div className="content">
            <div hidden={section !== "listening"}><Listening request={request} /></div>
          </div>
          <MiniPlayer openTrack={openTrack} />
        </main>
      </div>
      </NowPlayingContext.Provider>
    </TextsContext.Provider>
  );
}
