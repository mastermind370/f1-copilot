"use client";

import { useEffect, useState } from "react";
import { api, formatDate, type RuleInfo } from "@/lib/api";

export default function SourcesPage() {
  const [rules, setRules] = useState<RuleInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.rules().then(setRules).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <>
      <h1>Rules &amp; sources</h1>
      <p className="muted">
        Every date in your timeline comes from one of these rules. Each is a versioned file that
        links to the official page it came from and records when it was last checked.
      </p>
      {error && <div className="banner error">{error}</div>}
      {rules.map((r) => (
        <article key={r.id} className="card">
          <h3>
            {r.title} <span className="muted small">v{r.version}</span>
          </h3>
          <p>{r.summary}</p>
          <div className="muted small source-line">
            <a href={r.source_url} target="_blank" rel="noreferrer">
              Source{r.citation ? ` (${r.citation})` : ""}
            </a>{" "}
            · verified {formatDate(r.last_verified)}
            {r.verification === "secondary" && <span className="badge">secondary source</span>}
            {r.stale && <span className="badge warn">needs re-verification</span>}
          </div>
          {r.notes.length > 0 && (
            <ul className="notes">
              {r.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </>
  );
}
