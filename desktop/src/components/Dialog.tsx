/** Messages and questions over the window, in its own look (the Tk window used the system's message boxes). */

import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useTexts } from "../i18n";

interface Ask {
  title: string;
  message: string;
  question: boolean;
  answer: (yes: boolean) => void;
}

export interface Dialogs {
  alert: (title: string, message: string) => Promise<void>;
  confirm: (title: string, message: string) => Promise<boolean>;
}

const DialogContext = createContext<Dialogs>({
  alert: async () => {},
  confirm: async () => false,
});

export const useDialogs = () => useContext(DialogContext);

export function DialogProvider({ children }: { children: ReactNode }) {
  const { t } = useTexts();
  const [ask, setAsk] = useState<Ask | null>(null);
  const yesButton = useRef<HTMLButtonElement>(null);

  const alert = useCallback((title: string, message: string) => new Promise<void>((resolve) =>
    setAsk({ title, message, question: false, answer: () => resolve() })), []);
  const confirm = useCallback((title: string, message: string) => new Promise<boolean>((resolve) =>
    setAsk({ title, message, question: true, answer: resolve })), []);

  const close = (yes: boolean) => {
    ask?.answer(yes);
    setAsk(null);
  };

  useEffect(() => {
    if (!ask) return;
    yesButton.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close(false);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  });

  return (
    <DialogContext.Provider value={{ alert, confirm }}>
      {children}
      {ask && (
        <div className="dialog-backdrop" onMouseDown={(event) => event.target === event.currentTarget && close(false)}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
            <h2 id="dialog-title">{ask.title}</h2>
            <p>{ask.message}</p>
            <div className="dialog-buttons">
              {ask.question && <button className="button" onClick={() => close(false)}>{t("dialog.no")}</button>}
              <button ref={yesButton} className="button primary" onClick={() => close(true)}>
                {t(ask.question ? "dialog.yes" : "dialog.ok")}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}
