"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { type Lang, LANGS, type MessageKey, translate } from "@/lib/i18n";
import { findSchool, type School } from "@/lib/schools";
import { applyTheme, themeFor } from "@/lib/themes";

// Language and school are preferences, not personal facts, but they still live only in this
// browser. Nothing here is sent anywhere except the school id that scopes Q&A sources.
const KEY = "f1copilot.prefs.v1";

interface Prefs {
  ready: boolean; // true once saved preferences have been read
  lang: Lang;
  locale: string;
  school: School | null;
  setLang: (l: Lang) => void;
  setSchool: (id: string | null) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  pickerOpen: boolean;
  openPicker: () => void;
  closePicker: () => void;
}

const PrefsContext = createContext<Prefs | null>(null);

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used inside <Providers>");
  return ctx;
}

export default function Providers({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [schoolId, setSchoolId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) {
        const p = JSON.parse(raw) as { lang?: string; school?: string | null };
        if (LANGS.some((l) => l.code === p.lang)) setLangState(p.lang as Lang);
        if (findSchool(p.school)) setSchoolId(p.school ?? null);
      }
    } catch {
      /* storage unavailable: use defaults */
    }
    setReady(true);
  }, []);

  const persist = useCallback((next: { lang: Lang; school: string | null }) => {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* not remembered, still works */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : lang;
  }, [lang]);

  // Recolor the whole app in the student's school colors.
  useEffect(() => {
    applyTheme(themeFor(schoolId));
  }, [schoolId]);

  const value = useMemo<Prefs>(() => {
    const locale = LANGS.find((l) => l.code === lang)?.locale ?? "en-US";
    return {
      ready,
      lang,
      locale,
      school: findSchool(schoolId),
      setLang: (l) => {
        setLangState(l);
        persist({ lang: l, school: schoolId });
      },
      setSchool: (id) => {
        setSchoolId(id);
        persist({ lang, school: id });
      },
      t: (key, vars) => translate(lang, key, vars),
      pickerOpen,
      openPicker: () => setPickerOpen(true),
      closePicker: () => setPickerOpen(false),
    };
  }, [ready, lang, schoolId, pickerOpen, persist]);

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}
