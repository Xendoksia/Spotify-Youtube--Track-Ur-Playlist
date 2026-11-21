/** The account (api/account.py): a login card while logged out, the profile, syncing and this computer once
 * logged in; and the login screen covering the window when it opens without a remembered session. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { get, post } from "../api";
import Hero from "../components/Hero";
import Icon from "../components/Icon";
import Logo from "../components/Logo";
import { useTexts } from "../i18n";

export interface AccountData {
  configured: boolean;
  needs_login: boolean;
  remembered: boolean;
  busy: boolean;
  profile: {
    name: string;
    first_name: string;
    email: string;
    detail: string;
    avatar: string | null;
    details: { label: string; value: string }[];
  } | null;
  sync?: {
    state: "done" | "failed" | "waiting";
    text: string;
    when: string;
    counts: string;
    device: string;
    plays: string;
    waiting: string;
    all_sent: boolean;
    last_ok: string;
    stale: string;
    check: { lines: string[]; same: boolean; same_text?: string; at: string };
  };
}

interface AccountState {
  data: AccountData | null;
  reload: () => void;
  /** What an action is doing or why it failed, under its buttons */
  message: { text: string; error: boolean } | null;
}

export const AccountContext = createContext<AccountState>({ data: null, reload: () => {}, message: null });

/** The account, asked again after every action and sync, shared by the sidebar, the page and the login screen */
export function useAccountState(): AccountState {
  const [data, setData] = useState<AccountData | null>(null);
  const [message, setMessage] = useState<AccountState["message"]>(null);
  // The avatar is asked for again once a new one is saved
  const [avatar, setAvatar] = useState(0);
  const reload = useCallback(() => {
    get<AccountData>("/api/account").then(setData, () => {});
  }, []);
  useEffect(reload, [reload]);
  useEffect(() => window.tracker.onEvent((event) => {
    if (event.event === "account") {
      if (event.state === "busy") setMessage({ text: String(event.message), error: false });
      else if (event.state === "error") setMessage({ text: String(event.message), error: true });
      else if (event.state === "done") setMessage(event.message ? { text: String(event.message), error: false } : null);
      if (event.state === "avatar") setAvatar((count) => count + 1);
      reload();
    }
    if (event.event === "synced" || event.event === "plays") reload();
  }), [reload]);
  const withAvatar = data?.profile?.avatar
    ? { ...data, profile: { ...data.profile, avatar: `${data.profile.avatar}?v=${avatar}` } } : data;
  return { data: withAvatar, reload, message };
}

export const useAccount = () => useContext(AccountContext);

function Message() {
  const { message } = useAccount();
  if (!message?.text) return null;
  return <p className={message.error ? "account-message error" : "account-message muted"}>{message.text}</p>;
}

/** Covers the window when it opens logged out with an account service set up; closes once logged in or skipped */
export function LoginScreen({ onDone }: { onDone: () => void }) {
  const { t } = useTexts();
  const { data, reload } = useAccount();
  const [remember, setRemember] = useState(data?.remembered ?? true);
  useEffect(() => {
    if (data?.profile) onDone();
  }, [data?.profile, onDone]);
  return (
    <div className="login-screen">
      <div className="login-card">
        <Logo size={64} />
        <h1>{t("app.title")}</h1>
        <p className="muted">{t("login_screen.lead")}</p>
        <button className="button primary large" disabled={data?.busy}
                onClick={() => post("/api/account/login", { remember })}>
          {t("account.login_google")}
        </button>
        <label className="remember">
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
          {t("login_screen.remember")}
        </label>
        <Message />
        <hr />
        <button className="link-button" disabled={data?.busy} onClick={async () => {
          await post("/api/account/skip", {});
          reload();
          onDone();
        }}>
          {t("account.skip")}
        </button>
      </div>
    </div>
  );
}

export default function Account({ onLoggedOut }: { onLoggedOut: () => void }) {
  const { t } = useTexts();
  const { data } = useAccount();
  const [wasLoggedIn, setWasLoggedIn] = useState(false);
  // Logging out shows the login screen again, as in the Tk window
  useEffect(() => {
    if (data?.profile) setWasLoggedIn(true);
    else if (data && wasLoggedIn) {
      setWasLoggedIn(false);
      onLoggedOut();
    }
  }, [data, wasLoggedIn, onLoggedOut]);

  if (!data) return null;
  const profile = data.profile;
  return (
    <div className="page">
      <header className="toolbar"><h1 className="period-title">{t("account.title")}</h1></header>
      <div className="overview">
        {!data.configured && <p className="muted">{t("account.not_configured")}</p>}
        {data.configured && !profile && (
          <section className="card account-login">
            <h2>{t("account.login_title")}</h2>
            <p className="muted">{t("account.login_lead")}</p>
            <button className="button primary" disabled={data.busy} onClick={() => post("/api/account/login", {})}>
              {t("account.login_google")}
            </button>
            <Message />
          </section>
        )}
        {profile && data.sync && (
          <>
            <Hero round empty="" caption={t("account.caption")}
                  data={{ caption: t("account.caption"), title: profile.name, subtitle: profile.email,
                          detail: profile.detail, image: profile.avatar ?? "/api/avatar" }} />
            <div className="account-cards">
              <section className="card account-card">
                <h2 className="card-title"><Icon name="sync" />{t("account.sync")}</h2>
                <span className={`account-state sync-${data.sync.state}`}>● {data.sync.text}</span>
                {data.sync.when && <span className="muted">{data.sync.when}</span>}
                {data.sync.counts && (
                  <span className={data.sync.state === "failed" ? "event-removed" : ""}>{data.sync.counts}</span>
                )}
                {data.sync.last_ok && <span className="muted">{data.sync.last_ok}</span>}
                {data.sync.stale && <span className="event-removed">{data.sync.stale}</span>}
                <div className="card-buttons">
                  <button className="button primary" disabled={data.busy} onClick={() => post("/api/account/sync", {})}>
                    {t("account.sync_now")}
                  </button>
                </div>
              </section>
              <section className="card account-card">
                <h2 className="card-title"><Icon name="check" />{t("account.check")}</h2>
                {data.sync.check.same_text && <span className="account-state event-added">{data.sync.check.same_text}</span>}
                {data.sync.check.lines.map((line) => <span key={line}>{line}</span>)}
                {data.sync.check.at && <span className="muted">{data.sync.check.at}</span>}
                <div className="card-buttons">
                  <button className="button" disabled={data.busy} onClick={() => post("/api/account/check", {})}>
                    {t("account.check_now")}
                  </button>
                </div>
              </section>
              <section className="card account-card">
                <h2 className="card-title"><Icon name="device" />{t("account.device")}</h2>
                <span className="account-state">{data.sync.device}</span>
                <span className="muted">{data.sync.plays}</span>
                <span className={data.sync.all_sent ? "event-added" : ""}>{data.sync.waiting}</span>
              </section>
              <section className="card account-card">
                <h2 className="card-title"><Icon name="account" />{t("account.details")}</h2>
                <dl className="account-details">
                  {profile.details.map((item) => (
                    <div key={item.label}><dt className="muted">{item.label}</dt><dd>{item.value}</dd></div>
                  ))}
                </dl>
                <div className="card-buttons">
                  <button className="button" disabled={data.busy} onClick={() => post("/api/account/refresh", {})}>
                    {t("account.refresh")}
                  </button>
                  <button className="button" disabled={data.busy} onClick={() => post("/api/account/logout", {})}>
                    {t("account.logout")}
                  </button>
                </div>
              </section>
            </div>
            <Message />
          </>
        )}
      </div>
    </div>
  );
}
