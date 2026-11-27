"use client";

import { useState } from "react";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { clearAll } from "@/lib/local";

const SECTIONS = ["browser", "server", "analytics", "links"] as const;

export default function PrivacyPage() {
  const { t } = usePrefs();
  const [cleared, setCleared] = useState(false);
  return (
    <div className="page tool-page">
      <PageTitle title={t("privacy.title")} intro={t("privacy.intro")} />
      {SECTIONS.map((s) => (
        <section key={s} className="card">
          <h2>{t(`privacy.${s}Title` as MessageKey)}</h2>
          <p>{t(`privacy.${s}` as MessageKey)}</p>
        </section>
      ))}
      <button type="button" className="btn danger" onClick={() => { clearAll(); setCleared(true); }}>
        {t("privacy.clearAll")}
      </button>
      <p role="status" className="muted">{cleared ? t("privacy.cleared") : ""}</p>
    </div>
  );
}
