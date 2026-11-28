"use client";

import { type FormEvent, useEffect, useState } from "react";
import { ExternalIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import {
  approvalRate, type EmployerDetail, employerDetail, type EmployerHit, EmployersError, money, searchEmployers,
} from "@/lib/employers";
import type { MessageKey } from "@/lib/i18n";

const EVERIFY = "https://www.e-verify.gov/e-verify-employer-search";
const USCIS_HUB = "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub";
const DOL_DATA = "https://www.dol.gov/agencies/eta/foreign-labor/performance";

type Results = { kind: "idle" } | { kind: "loading" } | { kind: "ready"; hits: EmployerHit[] } | { kind: "error"; code: string };

function Detail({ k }: { k: string }) {
  const { t, locale } = usePrefs();
  const [d, setD] = useState<EmployerDetail | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    const ctl = new AbortController();
    employerDetail(k, ctl.signal).then(setD).catch((e) => e.name !== "AbortError" && setErr(e.code ?? "error"));
    return () => ctl.abort();
  }, [k]);
  if (err) return <p className="muted">{t(`emp.err.${err}` as MessageKey)}</p>;
  if (!d) return <p className="muted" aria-busy="true">{t("ask.searching")}</p>;
  return (
    <div className="emp-detail">
      <div className="emp-stats">
        <div><strong>{d.years[0] ? d.years[0].new_approved.toLocaleString(locale) : "—"}</strong>
          <span>{t("emp.newApprovedIn", { year: d.years[0]?.fy ?? "—" })}</span></div>
        <div><strong>{d.filings.toLocaleString(locale)}</strong><span>{t("emp.filings")}</span></div>
        <div><strong>{money(d.medianWage, locale)}</strong><span>{t("emp.medianSalary")}</span></div>
      </div>

      {d.years.length > 0 && (
        <>
          <h4>{t("emp.byYear")}</h4>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr>
                <th scope="col">{t("emp.fy")}</th><th scope="col">{t("emp.newApproved")}</th><th scope="col">{t("emp.newDenied")}</th>
                <th scope="col">{t("emp.rate")}</th><th scope="col">{t("emp.contApproved")}</th>
              </tr></thead>
              <tbody>
                {d.years.map((y) => {
                  const rate = approvalRate(y);
                  return (
                    <tr key={y.fy}>
                      <th scope="row">{y.fy}</th><td>{y.new_approved.toLocaleString(locale)}</td><td>{y.new_denied.toLocaleString(locale)}</td>
                      <td>{rate == null ? "—" : `${rate}%`}</td><td>{y.cont_approved.toLocaleString(locale)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {d.jobs.length > 0 && (
        <>
          <h4>{t("emp.jobs")}</h4>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr>
                <th scope="col">{t("emp.jobTitle")}</th><th scope="col">{t("emp.filings")}</th>
                <th scope="col">{t("emp.median")}</th><th scope="col">{t("emp.range")}</th>
              </tr></thead>
              <tbody lang="en">
                {d.jobs.map((j) => (
                  <tr key={j.title}>
                    <th scope="row">{j.title}</th><td>{j.filings.toLocaleString(locale)}</td><td>{money(j.medianWage, locale)}</td>
                    <td>{j.low != null && j.high != null ? `${money(j.low, locale)} – ${money(j.high, locale)}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {d.states.length > 0 && (
            <p className="muted small">{t("emp.whereFiled")} {d.states.map((s) => `${s.state} (${s.filings.toLocaleString(locale)})`).join(", ")}</p>
          )}
        </>
      )}
      {d.years.length === 0 && d.jobs.length === 0 && <p className="muted">{t("emp.noRecords")}</p>}

      <div className="emp-links">
        <a className="btn ghost small" href={EVERIFY} target="_blank" rel="noreferrer">{t("emp.checkEverify")} <ExternalIcon size={14} /></a>
        <a className="btn ghost small" href={USCIS_HUB} target="_blank" rel="noreferrer">{t("emp.uscisHub")} <ExternalIcon size={14} /></a>
      </div>
      <p className="muted small">{t("emp.everifyNote")}</p>
    </div>
  );
}

export default function EmployersPage() {
  const { t, locale } = usePrefs();
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [res, setRes] = useState<Results>({ kind: "idle" });
  const [open, setOpen] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setRes({ kind: "loading" });
    setOpen(null);
    try {
      const hits = await searchEmployers(q.trim(), state);
      setRes({ kind: "ready", hits });
      if (hits.length === 1) setOpen(hits[0].key);
    } catch (err) {
      setRes({ kind: "error", code: err instanceof EmployersError ? err.code : "error" });
    }
  };

  return (
    <div className="page tool-page">
      <PageTitle title={t("emp.title")} intro={t("emp.intro")} />
      <form className="card emp-search" onSubmit={submit} role="search">
        <div className="field grow">
          <label htmlFor="emp-q">{t("emp.company")}</label>
          <input id="emp-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("emp.placeholder")} autoComplete="organization" />
        </div>
        <div className="field">
          <label htmlFor="emp-state">{t("emp.state")}</label>
          <input id="emp-state" value={state} maxLength={2} size={4} placeholder="NJ"
            onChange={(e) => setState(e.target.value.toUpperCase().replace(/[^A-Z]/g, ""))} />
        </div>
        <button type="submit" className="btn">{t("emp.search")}</button>
      </form>

      <div aria-live="polite">
        {res.kind === "loading" && <p className="muted">{t("ask.searching")}</p>}
        {res.kind === "error" && (
          <div className="card empty-card">
            <p>{t(`emp.err.${res.code}` as MessageKey)}</p>
            {res.code === "employers_not_loaded" && (
              <a className="btn ghost small" href={USCIS_HUB} target="_blank" rel="noreferrer">{t("emp.uscisHub")} <ExternalIcon size={14} /></a>
            )}
          </div>
        )}
        {res.kind === "ready" && res.hits.length === 0 && <p className="card muted">{t("emp.none")}</p>}
        {res.kind === "ready" && res.hits.length > 0 && (
          <ul className="emp-list">
            {res.hits.map((h) => (
              <li key={h.key} className={`card emp-card ${open === h.key ? "is-open" : ""}`}>
                <button type="button" className="emp-head" aria-expanded={open === h.key} onClick={() => setOpen(open === h.key ? null : h.key)}>
                  <span className="emp-name">
                    <strong>{h.name}</strong>
                    <span className="muted small">{[h.city, h.state].filter(Boolean).join(", ")}</span>
                  </span>
                  <span className="emp-badges">
                    <span className={`pill ${h.new_recent > 0 ? "upcoming" : "doc-pill missing"}`}>
                      {t("emp.recentBadge", { n: h.new_recent.toLocaleString(locale) })}
                    </span>
                    {h.medianWage != null && <span className="pill doc-pill missing">{t("emp.medianBadge", { wage: money(h.medianWage, locale) })}</span>}
                  </span>
                  <span className="chev" aria-hidden="true">▾</span>
                </button>
                {open === h.key && <Detail k={h.key} />}
              </li>
            ))}
          </ul>
        )}
      </div>

      <section className="card">
        <h2>{t("emp.readTitle")}</h2>
        <ul className="small">
          <li>{t("emp.read1")}</li>
          <li>{t("emp.read2")}</li>
          <li>{t("emp.read3")}</li>
          <li>{t("emp.read4")}</li>
        </ul>
        <p className="muted small">
          {t("emp.sources")}{" "}
          <a href={USCIS_HUB} target="_blank" rel="noreferrer">USCIS H-1B Employer Data Hub</a> ·{" "}
          <a href={DOL_DATA} target="_blank" rel="noreferrer">DOL OFLC disclosure data</a>
        </p>
      </section>
    </div>
  );
}
