"use client";

import { useEffect, useState } from "react";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import { formatDate } from "@/lib/api";
import { loadJson, saveJson, todayIso } from "@/lib/local";
import { loadFacts } from "@/lib/storage";
import { countUnemployment, type Job } from "@/lib/unemployment";

interface OptState {
  eadStart: string;
  stem: boolean;
  jobs: Job[];
}

const KEY = "optdays.v1";

export default function OptDaysPage() {
  const { t, locale } = usePrefs();
  const [s, setS] = useState<OptState>({ eadStart: "", stem: false, jobs: [] });
  const [today, setToday] = useState("");

  useEffect(() => {
    setToday(todayIso());
    const saved = loadJson<OptState | null>(KEY, null);
    if (saved) return setS(saved);
    const f = loadFacts();
    setS({ eadStart: typeof f.opt_ead_start_date === "string" ? f.opt_ead_start_date : "", stem: f.on_stem_opt === true, jobs: [] });
  }, []);

  const update = (next: OptState) => {
    setS(next);
    saveJson(KEY, next);
  };
  const setJob = (id: string, patch: Partial<Job>) =>
    update({ ...s, jobs: s.jobs.map((j) => (j.id === id ? { ...j, ...patch } : j)) });

  const valid = s.eadStart && today && s.jobs.every((j) => j.start);
  const r = valid ? countUnemployment({ eadStart: s.eadStart, stem: s.stem, jobs: s.jobs, asOf: today }) : null;
  const pct = r ? Math.min(100, (r.used / r.limit) * 100) : 0;

  return (
    <div className="page tool-page">
      <PageTitle title={t("opt.title")} intro={t("opt.intro")} />

      <section className="card form-card">
        <div className="field">
          <label htmlFor="ead-start">{t("opt.eadStart")}</label>
          <input id="ead-start" type="date" value={s.eadStart} onChange={(e) => update({ ...s, eadStart: e.target.value })} />
        </div>
        <label className="check">
          <input type="checkbox" checked={s.stem} onChange={(e) => update({ ...s, stem: e.target.checked })} />
          {t("opt.stem")}
        </label>

        <h2>{t("opt.jobs")}</h2>
        {s.jobs.map((j, i) => (
          <fieldset key={j.id} className="job-row">
            <legend className="sr-only">{t("opt.jobs")} {i + 1}</legend>
            <div className="field">
              <label htmlFor={`${j.id}-s`}>{t("opt.jobStart")}</label>
              <input id={`${j.id}-s`} type="date" value={j.start} onChange={(e) => setJob(j.id, { start: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor={`${j.id}-e`}>{t("opt.jobEnd")}</label>
              <input id={`${j.id}-e`} type="date" value={j.end ?? ""} onChange={(e) => setJob(j.id, { end: e.target.value || null })} />
            </div>
            <label className="check">
              <input type="checkbox" checked={j.qualifies} onChange={(e) => setJob(j.id, { qualifies: e.target.checked })} />
              {t("opt.qualifies")}
            </label>
            <button type="button" className="btn ghost small" onClick={() => update({ ...s, jobs: s.jobs.filter((x) => x.id !== j.id) })}>
              {t("opt.remove")}
            </button>
          </fieldset>
        ))}
        <button type="button" className="btn ghost"
          onClick={() => update({ ...s, jobs: [...s.jobs, { id: `job-${Date.now()}`, start: "", end: null, qualifies: true }] })}>
          + {t("opt.addJob")}
        </button>
      </section>

      <section className="card meter-card" aria-live="polite">
        {!r ? (
          <p>{t("opt.enterStart")}</p>
        ) : r.status === "notStarted" ? (
          <p>{t("opt.notStarted")}</p>
        ) : (
          <>
            <div className="meter-nums">
              <strong className="meter-big">{t("opt.used", { used: r.used, limit: r.limit })}</strong>
              <span className={`pill ${r.status === "ok" ? "upcoming" : "active"}`}>{t("opt.remaining", { n: r.remaining })}</span>
            </div>
            <div className={`meter meter-${r.status}`} role="progressbar" aria-valuemin={0} aria-valuemax={r.limit}
              aria-valuenow={r.used} aria-label={t("opt.used", { used: r.used, limit: r.limit })}>
              <span style={{ width: `${pct}%` }} />
            </div>
            {r.status === "over" ? <p className="banner warn">{t("opt.over")}</p>
              : r.currentlyEmployed ? <p>{t("opt.employed")}</p>
              : r.limitDate && <p>{t("opt.limitDate", { date: formatDate(r.limitDate, locale) })}</p>}
          </>
        )}
      </section>

      <p className="muted">{t("opt.rules")}</p>
      <p className="muted small">
        <a href="https://studyinthestates.dhs.gov/sevis-help-hub/student-records/fm-student-employment/f-1-optional-practical-training-opt"
          target="_blank" rel="noreferrer">{t("opt.source")}</a> · {t("disclaimer")}
      </p>
    </div>
  );
}
