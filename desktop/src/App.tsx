import { useCallback, useEffect, useMemo, useState } from "react";
import { get } from "./api";
import Icon, { IconName } from "./components/Icon";
import { AppInfo, makeTexts, TextsContext } from "./i18n";
import Logo from "./components/Logo";
import MiniPlayer from "./components/MiniPlayer";
import { NowPlayingContext, useNowPlayingPoll } from "./nowPlaying";
import Listening, { OpenRequest } from "./pages/Listening";
import Playlists from "./pages/Playlists";
import Discover from "./pages/Discover";
import Account, { AccountContext, LoginScreen, useAccountState } from "./pages/Account";
import { DialogProvider } from "./components/Dialog";
import Marker from "./components/Marker";
import Help from "./pages/Help";
import Settings, { OpenSettingsContext } from "./pages/Settings";

type Section = "listening" | "playlists" | "discover" | "account" | "settings" | "help";

// The sections of the sidebar, as in the Tk window: the app's own at the top, the rest at the bottom
const SECTIONS: { name: Section; label: string; icon: IconName; bottom?: boolean }[] = [
  { name: "listening", label: "nav.listening", icon: "music" },
  { name: "playlists", label: "nav.playlists", icon: "list" },
  { name: "discover", label: "nav.discover", icon: "discover" },
  { name: "account", label: "nav.account", icon: "account", bottom: true },
  { name: "help", label: "nav.help", icon: "help", bottom: true },
  { name: "settings", label: "settings.title", icon: "settings", bottom: true },
];

// After a language or theme change the window is built again on the section it was on (?section=settings)
const START_SECTION = new URLSearchParams(location.search).get("section") as Section | null;

export default function App() {
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>(START_SECTION ?? "listening");
  const [settingsTab, setSettingsTab] = useState<"spotify" | "youtube" | "general">("general");
  const openSettings = useCallback((tab: "spotify" | "youtube" | "general" = "general") => {
    setSettingsTab(tab);
    setSection("settings");
  }, []);
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
  // Without any service's credentials the app opens on the settings, as in the Tk window
  useEffect(() => {
    if (START_SECTION) return;
    get<{ services: { has_credentials: boolean }[] }>("/api/services").then((result) => {
      if (!result.services.some((service) => service.has_credentials)) openSettings("spotify");
    }, () => {});
  }, [openSettings]);
  // A new language or theme, here or from another device: built again with its texts and colors
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event === "appearance") location.search = `?section=${section}`;
  }), [section]);

  // The mini player's song and Discover's artists open in the Listening section, from any section
  const openPage = (column: OpenRequest["column"], key: string) => {
    setSection("listening");
    setRequest((before) => ({ column, key, n: (before?.n ?? 0) + 1 }));
  };
  const openTrack = (key: string) => openPage("track_key", key);

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
      <OpenSettingsContext.Provider value={openSettings}>
      {/* Moves the window, along the top where Windows' title bar was; its buttons sit on the right */}
      <div className="title-bar" />
      <div className="shell">
        <nav className="sidebar">
          <Marker watch={section} />
          <div className="brand">
            <Logo size={30} />
            {t("app.title")}
          </div>
          {SECTIONS.map((item, index) => (
            <button
              key={item.name}
              className={`nav-item${section === item.name ? " selected" : ""}${
                item.bottom && !SECTIONS[index - 1]?.bottom ? " first-bottom" : ""}`}
              onClick={() => item.name === "settings" ? openSettings() : setSection(item.name)}
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
            <Discover hidden={section !== "discover"} openArtist={(key) => openPage("artist_key", key)} />
            <div hidden={section !== "account"}><Account onLoggedOut={() => setLoginScreen(true)} /></div>
            {section === "help" && <Help />}
            <Settings tab={settingsTab} setTab={setSettingsTab} hidden={section !== "settings"} />
          </div>
          <MiniPlayer openTrack={openTrack} />
        </main>
      </div>
      {loginScreen && <LoginScreen onDone={closeLogin} />}
      </OpenSettingsContext.Provider>
      </AccountContext.Provider>
      </DialogProvider>
      </NowPlayingContext.Provider>
    </TextsContext.Provider>
  );
}
