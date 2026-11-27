"use client";

import { type FormEvent, useState } from "react";
import AnswerView from "@/components/AnswerView";
import { api, type AskResponse } from "@/lib/api";

const EXAMPLES = [
  "When can I apply for post-completion OPT?",
  "Do I need a travel signature on my I-20 to re-enter the US?",
  "What is the I-901 SEVIS fee?",
  "我的I-20上需要有旅行签字才能重新入境美国吗？",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    try {
      setAnswer(await api.ask(trimmed));
    } catch (e) {
      setAnswer(null);
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <>
      <h1>Ask about F-1 rules</h1>
      <p className="muted">
        Answers use only official government and university pages, and every sentence links to
        its source. Ask in English, 中文, हिन्दी, 한국어 or Español.
      </p>
      <form onSubmit={onSubmit} className="ask-form">
        <label htmlFor="q" className="sr-only">
          Your question
        </label>
        <input
          id="q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How long can I stay after my program ends?"
          maxLength={1000}
          autoFocus
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>
      {!answer && !error && (
        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="chip"
              onClick={() => {
                setQuestion(ex);
                void ask(ex);
              }}
            >
              {ex}
            </button>
          ))}
        </div>
      )}
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}
      {answer && <AnswerView answer={answer} />}
      <p className="muted small">
        Need a date for your own situation? Use <a href="/timeline">My timeline</a>. Deadlines are
        computed by fixed rules, never by AI.
      </p>
    </>
  );
}
