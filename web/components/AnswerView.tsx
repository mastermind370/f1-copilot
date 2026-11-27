import type { ReactNode } from "react";
import type { AskResponse } from "@/lib/api";
import { formatDate } from "@/lib/api";

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
        {ids.map((id, i) => {
          const n = order.get(id);
          return n ? (
            <a key={id} href={`#src-${n}`} aria-label={`Source ${n}`}>
              {i > 0 ? "," : ""}
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
  if (answer.refused) {
    return (
      <section className="card refused">
        <h2>No reliable answer found</h2>
        <p>{answer.text}</p>
        <p className="muted small">
          Confidence {answer.confidence.toFixed(3)}. The tool refuses instead of guessing when the
          official sources it indexed don&apos;t cover a question.
        </p>
      </section>
    );
  }

  const order = new Map(answer.citations.map((c, i) => [c.chunk_id, i + 1]));
  const lines = answer.text.split("\n").filter((l) => l.trim());

  return (
    <section className="card">
      <div className="answer">
        {lines.map((line, i) => (
          <p key={i}>{renderWithCitations(line.replace(/^\s*[-•]\s*/, ""), order)}</p>
        ))}
      </div>
      <h3>Sources</h3>
      <ol className="sources">
        {answer.citations.map((c, i) => (
          <li key={c.chunk_id} id={`src-${i + 1}`}>
            <a href={c.url} target="_blank" rel="noreferrer">
              {c.heading || c.url}
            </a>
            <div className="muted small">
              {new URL(c.url).hostname} · retrieved {formatDate(c.retrieved_at.slice(0, 10))}
            </div>
            <details>
              <summary>Show passage</summary>
              <blockquote>{c.text}</blockquote>
            </details>
          </li>
        ))}
      </ol>
      <p className="muted small">
        Confidence {answer.confidence.toFixed(3)}
        {answer.cached ? " · cached answer" : ""}
      </p>
    </section>
  );
}
