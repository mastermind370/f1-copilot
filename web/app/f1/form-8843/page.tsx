"use client";

import { useEffect, useMemo, useState } from "react";
import { ExternalIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import { formatDate } from "@/lib/api";
import {
  type Answers8843, compute8843, defaultTaxYear, type ExemptVisa, guessPriorVisas, priorYears, type Stay,
} from "@/lib/form8843";
import { loadJson, saveJson, todayIso } from "@/lib/local";

const KEY = "form8843.v1";
const FORM_PDF = "https://www.irs.gov/pub/irs-pdf/f8843.pdf";
const VISAS: ExemptVisa[] = ["", "F", "J", "M", "Q"];

function blank(year: number, school: string, office: string): Answers8843 {
  return {
    taxYear: year, dependent: false, visa: "F-1", lastEntry: "", currentStatus: "F-1", statusChanged: "",
    citizenship: "", passportCountry: "", stays: [{ arrive: "", depart: null }], school, director: office,
    priorVisas: {}, appliedLPR: false, lprExplain: "", hadUsIncome: false,
  };
}

export default function Form8843Page() {
  const { t, locale, school } = usePrefs();
  const [a, setA] = useState<Answers8843 | null>(null);
  const [today, setToday] = useState("");

  useEffect(() => {
    setToday(todayIso());
    const saved = loadJson<Answers8843 | null>(KEY, null);
    setA(saved ?? blank(defaultTaxYear(), school?.name ?? "", school?.office ?? ""));
  }, [school]);

  const update = (patch: Partial<Answers8843>) => {
    setA((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...patch };
      saveJson(KEY, next);
      return next;
    });
  };
  const setStay = (i: number, patch: Partial<Stay>) =>
    a && update({ stays: a.stays.map((s, j) => (j === i ? { ...s, ...patch } : s)) });

  const ready = !!a && a.stays.some((s) => s.arrive);
  const result = useMemo(() => (a && ready && today ? compute8843(a, today) : null), [a, ready, today]);
  if (!a) return null;

  const thisYear = new Date().getFullYear();
  const years = [...new Set([thisYear, thisYear - 1, thisYear - 2, thisYear - 3, a.taxYear])].sort((x, y) => y - x);
  const prior = priorYears(a.taxYear);

  return (
    <div className="page tool-page form8843">
      <div className="no-print">
        <PageTitle title={t("f8843.title")} intro={t("f8843.intro")} />

        <section className="card form-card" aria-labelledby="f-about">
          <h2 id="f-about">{t("f8843.about")}</h2>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="f-year">{t("f8843.taxYear")}</label>
              <select id="f-year" value={a.taxYear} onChange={(e) => update({ taxYear: Number(e.target.value) })}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-visa">{t("f8843.visa")}</label>
              <select id="f-visa" value={a.visa} onChange={(e) => update({ visa: e.target.value, currentStatus: e.target.value, dependent: e.target.value.endsWith("2") })}>
                {["F-1", "J-1", "F-2", "J-2", "M-1"].map((v) => <option key={v}>{v}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="f-entry">{t("f8843.lastEntry")}</label>
              <input id="f-entry" type="date" value={a.lastEntry} onChange={(e) => update({ lastEntry: e.target.value })} />
              <span className="muted small">{t("f8843.lastEntryHelp")}</span>
            </div>
            <div className="field">
              <label htmlFor="f-change">{t("f8843.statusChanged")}</label>
              <input id="f-change" type="date" value={a.statusChanged} onChange={(e) => update({ statusChanged: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="f-cit">{t("f8843.citizenship")}</label>
              <input id="f-cit" value={a.citizenship} onChange={(e) => update({ citizenship: e.target.value })} autoComplete="country-name" />
            </div>
            <div className="field">
              <label htmlFor="f-pass">{t("f8843.passportCountry")}</label>
              <input id="f-pass" value={a.passportCountry} placeholder={a.citizenship} onChange={(e) => update({ passportCountry: e.target.value })} />
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={a.hadUsIncome} onChange={(e) => update({ hadUsIncome: e.target.checked })} />
            {t("f8843.income")}
          </label>
        </section>

        <section className="card form-card" aria-labelledby="f-stays">
          <h2 id="f-stays">{t("f8843.stays")}</h2>
          <p className="muted">{t("f8843.staysHelp")}</p>
          {a.stays.map((s, i) => (
            <fieldset key={i} className="job-row">
              <legend className="sr-only">{t("f8843.stays")} {i + 1}</legend>
              <div className="field">
                <label htmlFor={`s-a-${i}`}>{t("f8843.arrived")}</label>
                <input id={`s-a-${i}`} type="date" value={s.arrive} onChange={(e) => setStay(i, { arrive: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor={`s-d-${i}`}>{t("f8843.left")}</label>
                <input id={`s-d-${i}`} type="date" value={s.depart ?? ""} onChange={(e) => setStay(i, { depart: e.target.value || null })} />
              </div>
              {a.stays.length > 1 && (
                <button type="button" className="btn ghost small" onClick={() => update({ stays: a.stays.filter((_, j) => j !== i) })}>
                  {t("opt.remove")}
                </button>
              )}
            </fieldset>
          ))}
          <button type="button" className="btn ghost" onClick={() => update({ stays: [...a.stays, { arrive: "", depart: null }] })}>
            + {t("f8843.addStay")}
          </button>
          {result && (
            <p className="days-summary" aria-live="polite">
              {[a.taxYear, a.taxYear - 1, a.taxYear - 2].map((y) => (
                <span key={y}><strong>{result.daysByYear[y]}</strong> {t("f8843.daysIn", { year: y })}</span>
              ))}
            </p>
          )}
        </section>

        {!a.dependent && (
          <section className="card form-card" aria-labelledby="f-school">
            <h2 id="f-school">{t("f8843.schoolTitle")}</h2>
            <div className="field">
              <label htmlFor="f-l9">{t("f8843.line9")}</label>
              <textarea id="f-l9" rows={2} value={a.school} onChange={(e) => update({ school: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="f-l10">{t("f8843.line10")}</label>
              <textarea id="f-l10" rows={2} value={a.director} onChange={(e) => update({ director: e.target.value })} />
              <span className="muted small">{t("f8843.line10Help")}</span>
            </div>
            <fieldset className="visa-years">
              <legend>{t("f8843.line11")}</legend>
              <button type="button" className="btn ghost small" onClick={() => update({ priorVisas: guessPriorVisas(a.stays, a.taxYear) })}>
                {t("f8843.fillFromStays")}
              </button>
              <div className="visa-year-grid">
                {prior.map((y) => (
                  <div key={y} className="field">
                    <label htmlFor={`v-${y}`}>{y}</label>
                    <select id={`v-${y}`} value={a.priorVisas[y] ?? ""}
                      onChange={(e) => update({ priorVisas: { ...a.priorVisas, [y]: e.target.value as ExemptVisa } })}>
                      {VISAS.map((v) => <option key={v} value={v}>{v || t("f8843.notHere")}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </fieldset>
            <label className="check">
              <input type="checkbox" checked={a.appliedLPR} onChange={(e) => update({ appliedLPR: e.target.checked })} />
              {t("f8843.lpr")}
            </label>
            {a.appliedLPR && (
              <div className="field">
                <label htmlFor="f-l14">{t("f8843.lprExplain")}</label>
                <textarea id="f-l14" rows={2} value={a.lprExplain} onChange={(e) => update({ lprExplain: e.target.value })} />
              </div>
            )}
          </section>
        )}
      </div>

      {!result ? (
        <p className="card muted no-print">{t("f8843.needStay")}</p>
      ) : (
        <section className="card sheet" aria-labelledby="f-sheet">
          <h2 id="f-sheet">{t("f8843.sheetTitle", { year: a.taxYear })}</h2>
          <p className="muted small">{t("f8843.sheetIntro")}</p>
          {result.warnings.map((w) => <p key={w} className="banner warn" lang="en">{w}</p>)}
          <table className="sheet-table">
            <thead>
              <tr><th scope="col">{t("f8843.colLine")}</th><th scope="col">{t("f8843.colAsks")}</th><th scope="col">{t("f8843.colWrite")}</th></tr>
            </thead>
            <tbody lang="en">
              <tr className="sheet-group"><td colSpan={3}>{t("f8843.header")}</td></tr>
              <tr><td>{t("f8843.top")}</td><td>Your name, U.S. taxpayer ID (if any), addresses</td><td className="muted">{t("f8843.topHelp")}</td></tr>
              <tr className="sheet-group"><td colSpan={3}>Part I — General information</td></tr>
              {result.lines.filter((l) => Number.parseInt(l.line) <= 4).map((l) => <SheetRow key={l.line} l={l} />)}
              {!a.dependent && <>
                <tr className="sheet-group"><td colSpan={3}>Part II — Teachers and trainees: {t("f8843.skip")}</td></tr>
                <tr className="sheet-group"><td colSpan={3}>Part III — Students</td></tr>
                {result.lines.filter((l) => Number.parseInt(l.line) >= 9).map((l) => <SheetRow key={l.line} l={l} />)}
                <tr className="sheet-group"><td colSpan={3}>Parts IV and V: {t("f8843.skip")}</td></tr>
              </>}
            </tbody>
          </table>

          <div className="mail-card">
            <h3>{result.mail.withReturn ? t("f8843.mailWithReturn") : t("f8843.mailAlone")}</h3>
            {result.mail.withReturn ? (
              <p>{t("f8843.withReturnBody", { date: formatDate(result.mail.deadline, locale) })}</p>
            ) : (
              <>
                <p>{t("f8843.aloneBody", { date: formatDate(result.mail.deadline, locale) })}</p>
                <address lang="en">{result.mail.address.map((l) => <span key={l}>{l}<br /></span>)}</address>
                <ul className="small">
                  <li>{t("f8843.tip1")}</li>
                  <li>{t("f8843.tip2")}</li>
                  <li>{t("f8843.tip3")}</li>
                </ul>
              </>
            )}
          </div>

          <div className="sheet-actions no-print">
            <a className="btn" href={FORM_PDF} target="_blank" rel="noreferrer">{t("f8843.openForm")} <ExternalIcon size={16} /></a>
            <button type="button" className="btn ghost" onClick={() => window.print()}>{t("f8843.print")}</button>
          </div>
          <p className="muted small">
            {t("tax.notAdvice")} {t("f8843.sources")}{" "}
            <a href="https://www.irs.gov/forms-pubs/about-form-8843" target="_blank" rel="noreferrer">IRS: About Form 8843</a>
          </p>
        </section>
      )}
    </div>
  );
}

function SheetRow({ l }: { l: { line: string; label: string; value: string; note?: string } }) {
  return (
    <tr>
      <th scope="row">{l.line}</th>
      <td>{l.label}</td>
      <td>
        <strong className="sheet-value">{l.value || "—"}</strong>
        {l.note && <span className="sheet-note">{l.note}</span>}
      </td>
    </tr>
  );
}
