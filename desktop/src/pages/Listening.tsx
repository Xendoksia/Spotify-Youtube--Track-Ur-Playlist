/** The Listening section: the Statistics and Recently played tabs, and in their place the pages of tracks,
 * artists and albums opened from either, with back / forward between the pages visited. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTexts } from "../i18n";
import { Column, OpenDetailContext } from "../navigation";
import Detail, { DetailToolbar, Visit } from "./Detail";
import Overview from "./Overview";
import Recent from "./Recent";

type Tab = "stats" | "recent";

/** A page asked for from outside the section (the mini player); n tells two asks for the same page apart */
export interface OpenRequest extends Visit {
  n: number;
}

export default function Listening({ request }: { request: OpenRequest | null }) {
  const { t } = useTexts();
  const [tab, setTab] = useState<Tab>("stats");
  // The detail pages visited since the tab was left, and the one on display (-1: the tab)
  const [visits, setVisits] = useState<Visit[]>([]);
  const [index, setIndex] = useState(-1);
  const [detailTitle, setDetailTitle] = useState("");
  const tabScroll = useRef(0);

  const scroller = () => document.querySelector(".content");
  const openDetail = useCallback((column: Column, key: string) => {
    if (index < 0) tabScroll.current = scroller()?.scrollTop ?? 0;
    // Opening a page drops the pages that were ahead of the current one
    setVisits((before) => [...before.slice(0, index + 1), { column, key }]);
    setIndex(index + 1);
    scroller()?.scrollTo(0, 0);
  }, [index]);
  const closeDetail = useCallback(() => {
    setVisits([]);
    setIndex(-1);
    requestAnimationFrame(() => scroller()?.scrollTo(0, tabScroll.current));
  }, []);
  const step = useCallback((direction: number) => {
    // Back from the first page returns to the tab
    if (index + direction < 0) closeDetail();
    else if (index + direction < visits.length) {
      setIndex(index + direction);
      scroller()?.scrollTo(0, 0);
    }
  }, [index, visits.length, closeDetail]);

  const openRef = useRef(openDetail);
  openRef.current = openDetail;
  useEffect(() => {
    if (request) openRef.current(request.column, request.key);
  }, [request]);

  // Esc closes the page, Alt+Left and Alt+Right move between the pages visited, as in the Tk window
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (index < 0) return;
      if (event.key === "Escape") closeDetail();
      else if (event.altKey && event.key === "ArrowLeft") step(-1);
      else if (event.altKey && event.key === "ArrowRight") step(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, step, closeDetail]);

  const visit = index >= 0 ? visits[index] : null;
  return (
    <OpenDetailContext.Provider value={openDetail}>
      {!visit && (
        <nav className="tabs">
          {(["stats", "recent"] as Tab[]).map((name) => (
            <button key={name} className={tab === name ? "selected" : ""} onClick={() => setTab(name)}>
              {t(name === "stats" ? "stats.tab" : "listening.recent_tab")}
            </button>
          ))}
        </nav>
      )}
      {visit && (
        <div className="page">
          <DetailToolbar title={detailTitle} canForward={index < visits.length - 1}
                         onBack={() => step(-1)} onForward={() => step(1)} onClose={closeDetail} />
          <Detail key={`${visit.column}:${visit.key}`} visit={visit} onTitle={setDetailTitle} />
        </div>
      )}
      {/* Both tabs are kept while hidden, so they come back as they were left */}
      <Overview hidden={visit !== null || tab !== "stats"} />
      <Recent hidden={visit !== null || tab !== "recent"} />
    </OpenDetailContext.Provider>
  );
}
