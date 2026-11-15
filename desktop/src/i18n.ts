/** The interface texts, taken from the backend so both windows share one translation (core/i18n.py). */

import { createContext, useContext } from "react";

export interface AppInfo {
  language: string;
  theme: "system" | "light" | "dark";
  strings: Record<string, string>;
}

export interface Texts {
  t: (key: string, values?: Record<string, string | number>) => string;
  number: (value: number) => string;
  duration: (minutes: number) => string;
}

export function makeTexts(info: AppInfo): Texts {
  const numberFormat = new Intl.NumberFormat(info.language === "tr" ? "tr-TR" : "en-US");
  const t = (key: string, values: Record<string, string | number> = {}) =>
    (info.strings[key] ?? key).replace(/\{(\w+)\}/g, (match, name) => (name in values ? String(values[name]) : match));
  const number = (value: number) => numberFormat.format(Math.round(value));
  // As duration_text in ui/stats/text.py
  const duration = (minutes: number) => {
    const whole = Math.floor(minutes);
    const hours = Math.floor(whole / 60);
    return hours
      ? t("stats.hours_minutes", { hours: number(hours), minutes: whole % 60 })
      : t("stats.minutes", { minutes: whole });
  };
  return { t, number, duration };
}

export const TextsContext = createContext<Texts>(makeTexts({ language: "en", theme: "system", strings: {} }));

export const useTexts = () => useContext(TextsContext);
