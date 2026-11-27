"use client";

import { useEffect, useState } from "react";
import { usePrefs } from "@/components/Providers";
import { api, describeError, formatDate, type RuleInfo } from "@/lib/api";

export default function SourcesPage() {
  const { t, lang, locale } = usePrefs();
  const [rules, setRules] = useState<RuleInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.rules().then(setRules).catch((e: unknown) => setError(describeError(e, t)));
  }, [t]);

  return (
    <div className="page">
      <h1>{t("src.title")}</h1>
      <p className="lead">{t("src.intro")}</p>
      {lang !== "en" && <p className="muted small">{t("tl.englishNote")}</p>}
      {error && <div className="banner error">{error}</div>}
      <div className="rule-grid">
        {rules.map((r) => (
          <article key={r.id} className="card rule-card">
            <span className="eyebrow">{r.category}</span>
            <h3 lang="en">
              {r.title} <span className="muted small">v{r.version}</span>
            </h3>
            <p lang="en">{r.summary}</p>
            <div className="muted small source-line">
              <a href={r.source_url} target="_blank" rel="noreferrer">
                {t("tl.source")}{r.citation ? ` (${r.citation})` : ""}
              </a>{" "}
              · {t("tl.verified", { date: formatDate(r.last_verified, locale) })}
              {r.verification === "secondary" && <span className="badge">{t("tl.secondary")}</span>}
              {r.stale && <span className="badge warn">{t("src.needsReverify")}</span>}
            </div>
            {r.notes.length > 0 && (
              <ul className="notes" lang="en">
                {r.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
