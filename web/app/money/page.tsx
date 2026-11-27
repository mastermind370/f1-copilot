"use client";

import { BuildingIcon, MapPinIcon, PhoneIcon, WalletIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { LinkCard, NeedSchool, PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { mapsSearch, siteSearch } from "@/lib/links";

const BLOCKS: { title: MessageKey; items: MessageKey[]; Icon: typeof WalletIcon }[] = [
  { title: "money.bankTitle", items: ["money.b1", "money.b2", "money.b3", "money.b4"], Icon: BuildingIcon },
  { title: "money.creditTitle", items: ["money.c1", "money.c2", "money.c3"], Icon: WalletIcon },
  { title: "money.phoneTitle", items: ["money.p1", "money.p2", "money.p3"], Icon: PhoneIcon },
];

export default function MoneyPage() {
  const { t, school } = usePrefs();
  return (
    <div className="page">
      <PageTitle title={t("money.title")} intro={t("money.intro")} />
      <div className="tax-grid">
        {BLOCKS.map(({ title, items, Icon }) => (
          <section key={title} className="card">
            <h2 className="with-icon"><Icon size={20} /> {t(title)}</h2>
            <ul>{items.map((k) => <li key={k}>{t(k)}</li>)}</ul>
          </section>
        ))}
      </div>
      <h2>{t("money.near")}</h2>
      {school ? (
        <div className="link-grid">
          <LinkCard href={mapsSearch("bank", school.city)} icon={<MapPinIcon size={20} />} label={t("money.banks")} detail={school.city} />
          <LinkCard href={mapsSearch("credit union", school.city)} icon={<MapPinIcon size={20} />} label={t("money.creditUnions")} detail={school.city} />
          <LinkCard href={mapsSearch("cell phone store", school.city)} icon={<MapPinIcon size={20} />} label={t("money.phoneStores")} detail={school.city} />
          <LinkCard href={siteSearch("international students bank account", school.domain)} icon={<BuildingIcon size={20} />} label={t("money.schoolInfo")} detail={school.domain} />
        </div>
      ) : (
        <NeedSchool />
      )}
      <p className="muted small">{t("disclaimer")}</p>
    </div>
  );
}
