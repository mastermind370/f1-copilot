"use client";

import { PlaneIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { LinkCard, NeedSchool, PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { mapsDirections, mapsSearch, siteSearch } from "@/lib/links";

const TIPS: MessageKey[] = ["rides.t1", "rides.t2", "rides.t3", "rides.t4"];

export default function RidesPage() {
  const { t, school } = usePrefs();
  return (
    <div className="page">
      <PageTitle title={school ? t("rides.title", { city: school.city }) : t("nav.rides")} />
      {!school ? <NeedSchool /> : (
        <>
          <section>
            <h2>{t("rides.airports")}</h2>
            <div className="airport-grid">
              {school.airports.map((a) => (
                <article key={a.code} className="card airport">
                  <div className="airport-head">
                    <span className="airport-code">{a.code}</span>
                    <span className="airport-name">{a.name}</span>
                  </div>
                  <div className="row-actions">
                    <a className="btn" target="_blank" rel="noreferrer"
                      href={mapsDirections(`${a.code} airport`, school.name, "transit")}>
                      <PlaneIcon size={16} /> {t("rides.toCampus")}
                    </a>
                    <a className="btn ghost inline" target="_blank" rel="noreferrer"
                      href={mapsDirections(`${a.code} airport`, school.name, "driving")}>
                      {t("rides.driving")}
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h2>{t("rides.local")}</h2>
            <div className="link-grid">
              <LinkCard href={mapsSearch("taxi service", school.city)} icon="🚕" label={t("rides.taxi")} />
              <LinkCard href={mapsSearch("airport shuttle service", school.city)} icon="🚐" label={t("rides.shuttle")} />
              <LinkCard href={siteSearch("bus transit safe ride", school.domain)} icon="🚌" label={t("rides.transit")}
                detail={t("res.siteNote", { domain: school.domain })} />
            </div>
            <p className="muted small">{t("res.mapsNote", { city: school.city })}</p>
          </section>
        </>
      )}

      <section className="card">
        <h2>{t("rides.tipsTitle")}</h2>
        <ul className="check-list">{TIPS.map((k) => <li key={k}>{t(k)}</li>)}</ul>
      </section>
    </div>
  );
}
