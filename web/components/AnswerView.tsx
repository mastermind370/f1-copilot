"use client";

import type { ReactNode } from "react";
import { usePrefs } from "@/components/Providers";
import { type AskResponse, formatDate } from "@/lib/api";

const CITATION = /\[([0-9a-f]{12}(?:\s*,\s*[0-9a-f]{12})*)\]/g;

/** Replace [chunkid, chunkid] markers with numbered superscript links to the source list. */
function renderWithCitations(text: string, order: Map<string, number>): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(CITATION)) {
    const index = m.index ?? 0;
    if (index > last) nodes.push(text.slice(last, index));
    const ids = m[1].split(",").map((s) => s.trim());
    nodes.push(
      <sup key={`c${key++}`} className="cite">
        {ids.map((id) => {
          const n = order.get(id);
          return n ? (
            <a key={id} href={`#src-${n}`} aria-label={`Source ${n}`}>
              {n}
            </a>
          ) : null;
        })}
      </sup>,
    );
    last = index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export default function AnswerView({ answer }: { answer: AskResponse }) {
  const { t, lang, locale, school, openPicker } = usePrefs();

  if (answer.refused) {
    return (
      <section className="card answer-card refused">
        <h2>{t("ask.noAnswerTitle")}</h2>
        <p>{t("ask.noAnswerBody")}</p>
        {school ? (
          <a className="btn" href={school.url} target="_blank" rel="noreferrer">
            {t("ask.contactOffice", { office: school.office })}
          </a>
        ) : (
          <button type="button" className="btn" onClick={openPicker}>
            {t("school.choose")}
          </button>
        )}
        <p className="muted small">{t("ask.confidence", { value: answer.confidence.toFixed(3) })}</p>
      </section>
    );
  }

  const order = new Map(answer.citations.map((c, i) => [c.chunk_id, i + 1]));
  const lines = answer.text.split("\n").filter((l) => l.trim());

  return (
    <section className="card answer-card">
      <div className="answer">
        {lines.map((line, i) => (
          <p key={i}>{renderWithCitations(line.replace(/^\s*[-•]\s*/, ""), order)}</p>
        ))}
      </div>
      {lang !== "en" && <p className="muted small">{t("ask.englishNote")}</p>}
      <h3>{t("ask.sources")}</h3>
      <ol className="sources">
        {answer.citations.map((c, i) => (
          <li key={c.chunk_id} id={`src-${i + 1}`}>
            <a href={c.url} target="_blank" rel="noreferrer">
              {c.heading || c.url}
            </a>
            <div className="muted small">
              {new URL(c.url).hostname} · {t("ask.retrieved", { date: formatDate(c.retrieved_at.slice(0, 10), locale) })}
            </div>
            <details>
              <summary>{t("ask.showPassage")}</summary>
              <blockquote lang="en">{c.text}</blockquote>
            </details>
          </li>
        ))}
      </ol>
      <p className="muted small">
        {t("ask.confidence", { value: answer.confidence.toFixed(3) })}
        {answer.cached ? ` · ${t("ask.cached")}` : ""}
      </p>
    </section>
  );
}
