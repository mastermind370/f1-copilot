"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";

const KEY = "f1copilot.checklist.v1";

const SECTIONS: { title: MessageKey; items: MessageKey[] }[] = [
  { title: "guides.before", items: ["guides.b1", "guides.b2", "guides.b3", "guides.b4"] },
  { title: "guides.week", items: ["guides.w1", "guides.w2", "guides.w3", "guides.w4"] },
  { title: "guides.month", items: ["guides.m1", "guides.m2", "guides.m3", "guides.m4", "guides.m5"] },
];
const TOTAL = SECTIONS.reduce((n, s) => n + s.items.length, 0);

export default function GuidesPage() {
  const { t } = usePrefs();
  const [done, setDone] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setDone(JSON.parse(raw) as Record<string, boolean>);
    } catch {
      /* start empty */
    }
  }, []);

  function save(next: Record<string, boolean>) {
    setDone(next);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* not remembered */
    }
  }

  const count = Object.values(done).filter(Boolean).length;

  return (
    <div className="page">
      <PageTitle title={t("guides.title")} intro={t("guides.intro")} />
      <div className="progress-row">
        <div className="meter"><span style={{ width: `${(100 * count) / TOTAL}%` }} /></div>
        <span className="muted small">{t("guides.progress", { done: count, total: TOTAL })}</span>
      </div>
      <div className="guide-columns">
        {SECTIONS.map((s) => (
          <section key={s.title} className="card">
            <h2>{t(s.title)}</h2>
            <ul className="todo">
              {s.items.map((k) => (
                <li key={k}>
                  <label className={done[k] ? "done" : ""}>
                    <input type="checkbox" checked={Boolean(done[k])} onChange={(e) => save({ ...done, [k]: e.target.checked })} />
                    <span>{t(k)}</span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      <p className="hint">
        <Link href="/f1/ask">{t("guides.askMore")}</Link>
        {count > 0 && (
          <button type="button" className="btn ghost inline spaced-left" onClick={() => save({})}>{t("guides.reset")}</button>
        )}
      </p>
    </div>
  );
}
