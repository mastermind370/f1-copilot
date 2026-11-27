"use client";

import Link from "next/link";
import { BuildingIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { LinkCard, NeedSchool, PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { mapsSearch, siteSearch } from "@/lib/links";

const CHECKLIST: MessageKey[] = ["housing.c1", "housing.c2", "housing.c3", "housing.c4", "housing.c5", "housing.c6"];
const GLOSSARY = ["lease", "deposit", "utilities", "sublet", "guarantor"] as const;

export default function HousingPage() {
  const { t, school } = usePrefs();
  return (
    <div className="page">
      <PageTitle title={school ? t("housing.title", { school: school.short }) : t("nav.housing")} intro={t("housing.intro")} />
      {!school ? <NeedSchool /> : (
        <>
          <div className="link-grid">
            <LinkCard href={siteSearch("off-campus housing", school.domain)} icon={<BuildingIcon size={22} />}
              label={t("housing.official")} detail={t("res.siteNote", { domain: school.domain })} />
            <LinkCard href={mapsSearch("apartments for rent", school.name)} icon="🏢" label={t("housing.apartments")} />
            <LinkCard href={mapsSearch("furnished apartments", school.name)} icon="🛋️" label={t("housing.furnished")} />
            <LinkCard href={siteSearch("sublet housing", school.domain)} icon="🔑" label={t("housing.sublets")}
              detail={t("res.siteNote", { domain: school.domain })} />
          </div>
          <p className="muted small">{t("res.mapsNote", { city: school.city })}</p>
        </>
      )}

      <section className="card">
        <h2>{t("housing.checkTitle")}</h2>
        <ul className="check-list">
          {CHECKLIST.map((k) => <li key={k}>{t(k)}</li>)}
          <li><Link href="/f1/timeline">{t("housing.c7")}</Link></li>
        </ul>
      </section>

      <section>
        <h2>{t("housing.glossTitle")}</h2>
        <dl className="glossary">
          {GLOSSARY.map((g) => (
            <div key={g}>
              <dt>{t(`housing.g.${g}` as MessageKey)}</dt>
              <dd>{t(`housing.g.${g}Def` as MessageKey)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
