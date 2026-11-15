import { useCallback, useEffect, useMemo, useState } from "react";
import { get } from "./api";
import Icon, { IconName } from "./components/Icon";
import { AppInfo, makeTexts, TextsContext } from "./i18n";
import MiniPlayer from "./components/MiniPlayer";
import { NowPlayingContext, useNowPlayingPoll } from "./nowPlaying";
import Listening, { OpenRequest } from "./pages/Listening";
import Playlists from "./pages/Playlists";
import Account, { AccountContext, LoginScreen, useAccountState } from "./pages/Account";
import { DialogProvider } from "./components/Dialog";

type Section = "listening" | "playlists" | "account" | "settings" | "help";

// The sections of the Tk window's sidebar; the ones not moved over yet are greyed out
const SECTIONS: { name: Section; label: string; icon: IconName; ready: boolean }[] = [
  { name: "listening", label: "nav.listening", icon: "music", ready: true },
  { name: "playlists", label: "nav.playlists", icon: "list", ready: true },
  { name: "account", label: "nav.account", icon: "account", ready: true },
  { name: "help", label: "nav.help", icon: "help", ready: false },
  { name: "settings", label: "settings.title", icon: "settings", ready: false },
];

export default function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("listening");
  const [request, setRequest] = useState<OpenRequest | null>(null);
  const now = useNowPlayingPoll();
  const account = useAccountState();
  // The login screen covers the window when it opens logged out, once the account is known (not in the tray)
  const [loginScreen, setLoginScreen] = useState<boolean | null>(null);
  useEffect(() => {
    // Started in the tray: decided when the window is first shown
    const decide = () => {
      if (loginScreen === null && account.data && !document.hidden) setLoginScreen(account.data.needs_login);
    };
    decide();
    document.addEventListener("visibilitychange", decide);
    return () => document.removeEventListener("visibilitychange", decide);
  }, [account.data, loginScreen]);
  const closeLogin = useCallback(() => {
    setLoginScreen(false);
    setSection("listening");
  }, []);
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
      <DialogProvider>
      <AccountContext.Provider value={account}>
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
              {/* The account item shows the logged-in user's first name */}
              <span>{item.name === "account" && account.data?.profile ? account.data.profile.first_name : t(item.label)}</span>
            </button>
          ))}
        </nav>
        <main className="main">
          <div className="content">
            <div hidden={section !== "listening"}><Listening request={request} /></div>
            <div hidden={section !== "playlists"}><Playlists /></div>
            <div hidden={section !== "account"}><Account onLoggedOut={() => setLoginScreen(true)} /></div>
          </div>
          <MiniPlayer openTrack={openTrack} />
        </main>
      </div>
      {loginScreen && <LoginScreen onDone={closeLogin} />}
      </AccountContext.Provider>
      </DialogProvider>
      </NowPlayingContext.Provider>
    </TextsContext.Provider>
  );
}
