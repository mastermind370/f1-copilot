"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import FactsForm from "@/components/FactsForm";
import { usePrefs } from "@/components/Providers";
import TimelineView from "@/components/TimelineView";
import { api, describeError, type FactField, type FactValue, type Facts, type Timeline } from "@/lib/api";
import { clearFacts, loadFacts, saveFacts } from "@/lib/storage";

export default function TimelinePage() {
  const { t } = usePrefs();
  const [schema, setSchema] = useState<FactField[]>([]);
  const [facts, setFacts] = useState<Facts>({});
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);
  const loaded = useRef(false);

  // The form comes from the API; the student's facts come from this browser only.
  useEffect(() => {
    setFacts(loadFacts());
    loaded.current = true;
    api.factsSchema().then(setSchema).catch((e: unknown) => setError(describeError(e, t)));
  }, [t]);

  const compute = useCallback(
    async (f: Facts) => {
      try {
        setTimeline(await api.timeline(f));
        setError(null);
      } catch (e) {
        setError(describeError(e, t));
      }
    },
    [t],
  );

  // Recompute (debounced) whenever facts change, and persist them locally.
  useEffect(() => {
    if (!loaded.current || schema.length === 0) return;
    setSaved(saveFacts(facts));
    const timer = setTimeout(() => void compute(facts), 300);
    return () => clearTimeout(timer);
  }, [facts, schema, compute]);

  function onChange(name: string, value: FactValue | null) {
    setFacts((prev) => {
      const next = { ...prev };
      if (value === null) delete next[name];
      else next[name] = value;
      return next;
    });
  }

  function onClear() {
    if (!window.confirm(t("tl.clearConfirm"))) return;
    clearFacts();
    setFacts({});
  }

  return (
    <div className="page">
      <h1>{t("tl.title")}</h1>
      <p className="lead">{t("tl.intro")}</p>
      <p className="privacy-note">
        <span aria-hidden="true">🔒</span> {t("tl.privacy")}
        {!saved && ` ${t("tl.storageBlocked")}`}
      </p>
      {error && <div className="banner error" role="alert">{error}</div>}
      <div className="two-col">
        <div>
          {schema.length > 0 && <FactsForm schema={schema} facts={facts} onChange={onChange} />}
          <button type="button" className="btn ghost" onClick={onClear}>{t("tl.clear")}</button>
        </div>
        <div>{timeline && <TimelineView timeline={timeline} schema={schema} />}</div>
      </div>
    </div>
  );
}
