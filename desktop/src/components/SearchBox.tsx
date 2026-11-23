/** A search box in the statistics' toolbar: it searches the recorded tracks, artists and albums once typing pauses
 * (or at once on Enter) and lists them under it, a result opening its page (api/search.py). */

import { useEffect, useRef, useState } from "react";
import { get } from "../api";
import { useTexts } from "../i18n";
import { Column, useOpenDetail } from "../navigation";
import Icon from "./Icon";
import Picture from "./Picture";

interface Result {
  key: string;
  column: Column;
  title: string;
  subtitle: string;
  value_text: string;
  image: string;
  round?: boolean;
}

interface Results {
  query: string;
  tracks: Result[];
  artists: Result[];
  albums: Result[];
}

// How long typing has to pause before the search runs
const PAUSE_MS = 400;
const MIN_LENGTH = 2;

export default function SearchBox() {
  const { t } = useTexts();
  const open = useOpenDetail();
  const [text, setText] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [shown, setShown] = useState(false);
  const latest = useRef(0);
  const box = useRef<HTMLDivElement>(null);

  const run = (query: string) => {
    const request = ++latest.current;
    if (query.trim().length < MIN_LENGTH) {
      setResults(null);
      return;
    }
    get<Results>("/api/search", { q: query.trim() }).then((found) => {
      if (request === latest.current) {
        setResults(found);
        setShown(true);
      }
    }, () => undefined);
  };

  // The search runs once typing pauses
  useEffect(() => {
    const timer = setTimeout(() => run(text), PAUSE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  // A click elsewhere closes the results
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setShown(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (result: Result) => {
    setShown(false);
    setText("");
    setResults(null);
    open?.(result.column, result.key);
  };

  const groups: [string, Result[]][] = results
    ? [[t("search.tracks"), results.tracks], [t("search.artists"), results.artists], [t("search.albums"), results.albums]]
    : [];
  const none = results !== null && groups.every(([, rows]) => !rows.length);
  return (
    <div className="search" ref={box}>
      <span className="search-icon"><Icon name="search" /></span>
      <input
        type="search"
        id="stats-search"
        value={text}
        placeholder={t("search.placeholder")}
        aria-label={t("search.placeholder")}
        autoComplete="off"
        spellCheck={false}
        onChange={(event) => setText(event.target.value)}
        onFocus={() => results && setShown(true)}
        onKeyDown={(event) => {
          if (event.key === "Enter") run(text);
          if (event.key === "Escape") {
            setShown(false);
            (event.target as HTMLInputElement).blur();
          }
        }}
      />
      {shown && results && (
        <div className="search-results" role="listbox">
          {none && <p className="search-none">{t("search.none")}</p>}
          {groups.filter(([, rows]) => rows.length).map(([title, rows]) => (
            <section key={title} className="search-group">
              <h3 className="search-group-title">{title}</h3>
              {rows.map((result) => (
                <button key={`${result.column}${result.key}`} className="search-result" role="option"
                        aria-selected={false} onClick={() => pick(result)}>
                  <Picture src={result.image} alt={result.title} round={result.round} className="search-picture" />
                  <span className="search-text">
                    <span className="search-title">{result.title}</span>
                    <span className="search-subtitle">{result.subtitle}</span>
                  </span>
                  <span className="search-value">{result.value_text}</span>
                </button>
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
