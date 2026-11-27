"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import FactsForm from "@/components/FactsForm";
import TimelineView from "@/components/TimelineView";
import { api, type FactField, type FactValue, type Facts, type Timeline } from "@/lib/api";
import { clearFacts, loadFacts, saveFacts } from "@/lib/storage";

export default function TimelinePage() {
  const [schema, setSchema] = useState<FactField[]>([]);
  const [facts, setFacts] = useState<Facts>({});
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);
  const loaded = useRef(false);

  // Load the form schema from the API and the user's facts from this browser only.
  useEffect(() => {
    setFacts(loadFacts());
    loaded.current = true;
    api.factsSchema().then(setSchema).catch((e: Error) => setError(e.message));
  }, []);

  const compute = useCallback(async (f: Facts) => {
    try {
      setTimeline(await api.timeline(f));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }, []);

  // Recompute (debounced) whenever facts change, and persist them locally.
  useEffect(() => {
    if (!loaded.current || schema.length === 0) return;
    setSaved(saveFacts(facts));
    const t = setTimeout(() => void compute(facts), 300);
    return () => clearTimeout(t);
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
    if (!window.confirm("Remove all your saved facts from this browser?")) return;
    clearFacts();
    setFacts({});
  }

  return (
    <>
      <h1>My F-1 timeline</h1>
      <p className="muted">
        Enter what you know. Leave the rest blank, and the timeline will tell you what each date
        still needs. Your answers are saved <strong>only in this browser</strong>. They are sent
        to your local Copilot API just to compute dates and are never stored there.
        {!saved && " (This browser blocked local storage, so your answers won't be remembered.)"}
      </p>
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}
      <div className="two-col">
        <div>
          {schema.length > 0 && <FactsForm schema={schema} facts={facts} onChange={onChange} />}
          <button type="button" className="secondary" onClick={onClear}>
            Clear my data
          </button>
        </div>
        <div>{timeline && <TimelineView timeline={timeline} schema={schema} />}</div>
      </div>
    </>
  );
}
