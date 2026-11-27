"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LangSwitch } from "@/components/Header";
import { ArrowRightIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import SchoolGrid from "@/components/SchoolGrid";

// "Hello" in the languages of the largest international student communities on Big Ten
// campuses, plus a few more. Each shows in its own script, like a new-device welcome.
const HELLOS: { text: string; lang: string; dir?: "rtl" }[] = [
  { text: "hello", lang: "en" },
  { text: "你好", lang: "zh" },
  { text: "नमस्ते", lang: "hi" },
  { text: "안녕하세요", lang: "ko" },
  { text: "hola", lang: "es" },
  { text: "こんにちは", lang: "ja" },
  { text: "xin chào", lang: "vi" },
  { text: "مرحبا", lang: "ar", dir: "rtl" },
  { text: "bonjour", lang: "fr" },
  { text: "নমস্কার", lang: "bn" },
  { text: "olá", lang: "pt" },
  { text: "merhaba", lang: "tr" },
  { text: "வணக்கம்", lang: "ta" },
  { text: "halo", lang: "id" },
  { text: "سلام", lang: "fa", dir: "rtl" },
  { text: "привет", lang: "ru" },
  { text: "habari", lang: "sw" },
  { text: "నమస్కారం", lang: "te" },
];

const INTERVAL_MS = 1800;

export default function WelcomePage() {
  const { ready, school, setSchool, t } = usePrefs();
  const router = useRouter();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setI((n) => (n + 1) % HELLOS.length), INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  // The welcome screen shows on every visit. Returning students get a one-tap Continue.
  if (!ready) return <div className="welcome" />;

  const hello = HELLOS[i];

  return (
    <div className="welcome">
      <div className="welcome-top">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true">F-1</span>
          <span className="brand-name">Copilot</span>
        </span>
        <LangSwitch />
      </div>

      <div className="hello-stage" aria-live="off">
        <span key={i} className="hello-word" lang={hello.lang} dir={hello.dir}>
          {hello.text}
        </span>
        <span className="sr-only">Hello</span>
      </div>

      <p className="welcome-tagline">{t("welcome.tagline")}</p>

      {school && (
        <>
          <button type="button" className="continue-btn" onClick={() => router.push("/home")}>
            <span className="mono">{school.mono}</span>
            {t("welcome.continue", { school: school.short })}
            <span className="go"><ArrowRightIcon size={18} /></span>
          </button>
          <p className="welcome-or">{t("welcome.orPick")}</p>
        </>
      )}

      <section className="welcome-schools">
        <h1>{school ? t("welcome.switch") : t("welcome.pick")}</h1>
        <SchoolGrid onPick={(s) => { setSchool(s.id); router.push("/home"); }} />
        <p className="muted small center">{t("welcome.later")}</p>
      </section>
    </div>
  );
}
