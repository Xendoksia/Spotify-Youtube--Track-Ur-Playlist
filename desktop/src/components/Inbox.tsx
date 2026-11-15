/** The notifications box: a bell with the number of summaries waiting on it, and the card it opens under itself.
 * It holds the monthly and yearly summaries not seen yet (api/wrapped.py inbox); opening one takes it out. */

import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import { useTexts } from "../i18n";
import Icon from "./Icon";

interface Item {
  id: string;
  title: string;
  detail: string;
}

export default function Inbox({ openSummary, version }: { openSummary: (id: string) => void; version: number }) {
  const { t, number } = useTexts();
  const [items, setItems] = useState<Item[]>([]);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    get<{ items: Item[] }>("/api/inbox").then((result) => setItems(result.items), () => {});
  }, []);
  // version changes when a summary was opened, which takes it out of the box
  useEffect(load, [load, version]);
  // A summary became ready, or was seen on another device
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event === "inbox" || message.event === "synced") load();
  }), [load]);
  // When the month turns while the window is open
  useEffect(() => {
    const onVisible = () => !document.hidden && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  // A click anywhere else or Esc closes the card
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="inbox" ref={box}>
      <button className={`icon-button bell${open ? " selected" : ""}`} aria-label={t("inbox.title")}
              onClick={() => {
                if (!open) load();
                setOpen(!open);
              }}>
        <Icon name="bell" />
        {items.length > 0 && <span className="badge">{number(items.length)}</span>}
      </button>
      {open && (
        <div className="inbox-card">
          <header className="inbox-header">
            <span>{t("inbox.title")}</span>
            {items.length > 0 && <span className="inbox-new">{t("inbox.new", { count: number(items.length) })}</span>}
          </header>
          {items.length === 0 ? (
            <div className="inbox-empty">
              <Icon name="bell" />
              <strong>{t("inbox.empty")}</strong>
              <span className="muted">{t("inbox.empty.detail")}</span>
            </div>
          ) : items.map((item) => (
            <button key={item.id} className="inbox-item" onClick={() => {
              setOpen(false);
              openSummary(item.id);
            }}>
              <span className="inbox-dot" />
              <span className="inbox-text">
                <strong>{item.title}</strong>
                <span className="muted">{item.detail}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
