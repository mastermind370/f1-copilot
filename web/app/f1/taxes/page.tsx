"use client";

import Link from "next/link";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import TaxBanner from "@/components/TaxBanner";
import type { MessageKey } from "@/lib/i18n";
import { siteSearch } from "@/lib/links";

const IRS = [
  { label: "Form 8843", url: "https://www.irs.gov/forms-pubs/about-form-8843" },
  { label: "Form 1040-NR", url: "https://www.irs.gov/forms-pubs/about-form-1040-nr" },
  { label: "Substantial presence test", url: "https://www.irs.gov/individuals/international-taxpayers/substantial-presence-test" },
  { label: "Tax treaties", url: "https://www.irs.gov/individuals/international-taxpayers/tax-treaties" },
  { label: "Publication 519", url: "https://www.irs.gov/publications/p519" },
];

export default function TaxesPage() {
  const { t, school } = usePrefs();
  const cards = [1, 2, 3, 4, 5, 6];
  return (
    <div className="page tool-page">
      <PageTitle title={t("tax.title")} intro={t("tax.intro")} />
      <TaxBanner />
      <section className="card helper-cta">
        <div>
          <h2>{t("tax.helperTitle")}</h2>
          <p>{t("tax.helperBody")}</p>
        </div>
        <Link className="btn" href="/f1/form-8843">{t("tax.helperCta")}</Link>
      </section>
      <div className="tax-grid">
        {cards.map((n) => (
          <section key={n} className="card">
            <h2>{t(`tax.t${n}Title` as MessageKey)}</h2>
            <p>{t(`tax.t${n}` as MessageKey)}</p>
            {n === 5 && school && (
              <a href={siteSearch("nonresident tax software", school.domain)} target="_blank" rel="noreferrer">{school.office}</a>
            )}
          </section>
        ))}
      </div>
      <section className="card">
        <h2>{t("tax.sources")}</h2>
        <ul className="link-list">
          {IRS.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer" lang="en">{s.label}</a></li>)}
        </ul>
      </section>
      <p className="muted small">{t("tax.notAdvice")} {t("disclaimer")}</p>
    </div>
  );
}
