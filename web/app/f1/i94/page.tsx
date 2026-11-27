"use client";

import { ExternalIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";

export default function I94Page() {
  const { t, school } = usePrefs();
  return (
    <div className="page tool-page">
      <PageTitle title={t("i94.title")} intro={t("i94.intro")} />
      <section className="card">
        <h2>{t("i94.stepsTitle")}</h2>
        <ol className="steps">
          <li>{t("i94.s1")}</li>
          <li>{t("i94.s2")}</li>
          <li>{t("i94.s3")}</li>
          <li>{t("i94.s4")}</li>
        </ol>
        <a className="btn" href="https://i94.cbp.dhs.gov/" target="_blank" rel="noreferrer">
          {t("i94.open")} <ExternalIcon size={16} />
        </a>
        <p className="muted small">{t("i94.scam")}</p>
      </section>
      <section className="card">
        <h2>{t("i94.checkTitle")}</h2>
        <ul className="checks">
          <li>{t("i94.c1")}</li>
          <li>{t("i94.c2")}</li>
          <li>{t("i94.c3")}</li>
          <li>{t("i94.c4")}</li>
        </ul>
        <p className="banner info">{t("i94.dsNote")}</p>
      </section>
      <section className="card">
        <h2>{t("i94.fixTitle")}</h2>
        <p>{t("i94.fix")}</p>
        {school && <a href={school.url} target="_blank" rel="noreferrer">{school.office}</a>}
      </section>
      <p className="muted small">{t("disclaimer")}</p>
    </div>
  );
}
