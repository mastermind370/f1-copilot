"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AnswerView from "@/components/AnswerView";
import AskBar from "@/components/AskBar";
import { usePrefs } from "@/components/Providers";
import { api, type AskResponse, describeError } from "@/lib/api";

function AskInner() {
  const { t, school } = usePrefs();
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const lastAsked = useRef<string | null>(null);

  const run = useCallback(
    async (question: string) => {
      setLoading(true);
      setError(null);
      try {
        setAnswer(await api.ask(question, school?.id ?? null));
      } catch (e) {
        setAnswer(null);
        setError(describeError(e, t));
      } finally {
        setLoading(false);
      }
    },
    [school, t],
  );

  // The question lives in the URL, so answers can be bookmarked and the back button works.
  useEffect(() => {
    const key = `${q}|${school?.id ?? ""}`;
    if (q && lastAsked.current !== key) {
      lastAsked.current = key;
      void run(q);
    }
  }, [q, school, run]);

  return (
    <div className="page">
      <h1>{t("ask.title")}</h1>
      <p className="lead">{t("ask.intro")}</p>
      <AskBar initial={q} busy={loading} autoFocus={!q}
        onAsk={(question) => router.push(`/f1/ask?q=${encodeURIComponent(question)}`)} />
      {loading && <p className="muted">{t("ask.searching")}</p>}
      {error && <div className="banner error" role="alert">{error}</div>}
      {answer && !loading && <AnswerView answer={answer} />}
      <p className="muted small hint">
        <Link href="/f1/timeline">{t("nav.timeline")}</Link> · {t("ask.timelineHint")}
      </p>
    </div>
  );
}

export default function AskPage() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return (
    <Suspense fallback={null}>
      <AskInner />
    </Suspense>
  );
}
