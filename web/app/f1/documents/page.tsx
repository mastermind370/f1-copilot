"use client";

import { useEffect, useState } from "react";
import { CalendarIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import { formatDate } from "@/lib/api";
import { DOCS, type DocId, docStatus, signatureExpiry } from "@/lib/documents";
import type { MessageKey } from "@/lib/i18n";
import { type CalEvent, downloadIcs } from "@/lib/ics";
import { loadJson, saveJson, todayIso } from "@/lib/local";
import { loadFacts } from "@/lib/storage";

interface DocState {
  dates: Partial<Record<DocId, string>>;
  signed?: string;
  onOpt: boolean;
}

const KEY = "documents.v1";

export default function DocumentsPage() {
  const { t, locale } = usePrefs();
  const [state, setState] = useState<DocState>({ dates: {}, onOpt: false });
  const [today, setToday] = useState("");

  useEffect(() => {
    setToday(todayIso());
    const saved = loadJson<DocState | null>(KEY, null);
    if (saved) return setState(saved);
    // First visit: prefill from the timeline answers already saved in this browser.
    const f = loadFacts();
    setState({
      dates: {
        i20: typeof f.program_end_date === "string" ? f.program_end_date : undefined,
        ead: typeof f.opt_ead_end_date === "string" ? f.opt_ead_end_date : undefined,
      },
      signed: typeof f.last_travel_signature_date === "string" ? f.last_travel_signature_date : undefined,
      onOpt: f.on_opt === true || f.on_stem_opt === true,
    });
  }, []);

  const update = (next: DocState) => {
    setState(next);
    saveJson(KEY, next);
  };

  const expiry = (id: DocId) =>
    id === "signature" ? (state.signed ? signatureExpiry(state.signed, state.onOpt) : undefined) : state.dates[id];

  const events: CalEvent[] = DOCS.flatMap((id) => {
    const date = expiry(id);
    if (!date || !today || date < today) return [];
    const doc = t(`docs.${id}` as MessageKey);
    return [{ uid: `doc-${id}-${date}`, date, title: t("docs.reminder", { doc }),
      description: t(`docs.${id}Note` as MessageKey), remindDaysBefore: [90, 30, 7] }];
  });

  return (
    <div className="page tool-page">
      <PageTitle title={t("docs.title")} intro={t("docs.intro")} />
      <div className="doc-list">
        {DOCS.map((id) => {
          const date = expiry(id);
          const raw = today ? docStatus(date, today) : { status: "missing" as const, days: null };
          // A visa may expire while you're in the US; it only matters for re-entry, so no alarm.
          const visaOnly = id === "visa" && raw.status === "expired";
          const s = { ...raw, cls: visaOnly ? "missing" : raw.status };
          const inputId = `doc-${id}`;
          return (
            <section key={id} className={`card doc doc-${s.cls}`} aria-labelledby={`${inputId}-h`}>
              <div className="doc-head">
                <h2 id={`${inputId}-h`}>{t(`docs.${id}` as MessageKey)}</h2>
                <span className={`pill doc-pill ${s.cls}`}>
                  {visaOnly ? t("docs.status.visaExpired") : t(`docs.status.${s.status}` as MessageKey, { n: Math.abs(s.days ?? 0) })}
                </span>
              </div>
              <p className="muted">{t(`docs.${id}Note` as MessageKey)}</p>
              {id === "signature" ? (
                <div className="doc-fields">
                  <label htmlFor={inputId}>{t("docs.signedOn")}</label>
                  <input id={inputId} type="date" value={state.signed ?? ""}
                    onChange={(e) => update({ ...state, signed: e.target.value || undefined })} />
                  <label className="check">
                    <input type="checkbox" checked={state.onOpt} onChange={(e) => update({ ...state, onOpt: e.target.checked })} />
                    {t("docs.onOpt")}
                  </label>
                  {date && <span className="muted small">{t("docs.expires")}: {formatDate(date, locale)}</span>}
                </div>
              ) : (
                <div className="doc-fields">
                  <label htmlFor={inputId}>{t("docs.expires")}</label>
                  <input id={inputId} type="date" value={state.dates[id] ?? ""}
                    onChange={(e) => update({ ...state, dates: { ...state.dates, [id]: e.target.value || undefined } })} />
                </div>
              )}
            </section>
          );
        })}
      </div>
      {events.length > 0 && (
        <button type="button" className="btn" onClick={() => downloadIcs("f1-documents.ics", events)}>
          <CalendarIcon size={18} /> {t("docs.export")}
        </button>
      )}
      <p className="card tip">{t("docs.keep")}</p>
      <p className="muted small">{t("disclaimer")}</p>
    </div>
  );
}
