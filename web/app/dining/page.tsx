"use client";

import { usePrefs } from "@/components/Providers";
import PlaceDropdown from "@/components/PlaceDropdown";
import { LinkCard, NeedSchool, PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { mapsSearch, siteSearch } from "@/lib/links";

const CUISINES: { key: MessageKey; emoji: string; query: string }[] = [
  { key: "dine.indian", emoji: "🍛", query: "Indian restaurant" },
  { key: "dine.chinese", emoji: "🥡", query: "Chinese restaurant" },
  { key: "dine.korean", emoji: "🍲", query: "Korean restaurant" },
  { key: "dine.japanese", emoji: "🍣", query: "Japanese restaurant" },
  { key: "dine.thai", emoji: "🍤", query: "Thai restaurant" },
  { key: "dine.vietnamese", emoji: "🍜", query: "Vietnamese pho restaurant" },
  { key: "dine.hotpot", emoji: "♨️", query: "hot pot restaurant" },
  { key: "dine.nepali", emoji: "🥟", query: "Nepali restaurant" },
  { key: "dine.mideast", emoji: "🧆", query: "Middle Eastern restaurant" },
  { key: "dine.turkish", emoji: "🥙", query: "Turkish restaurant" },
  { key: "dine.ethiopian", emoji: "🫓", query: "Ethiopian restaurant" },
  { key: "dine.mexican", emoji: "🌮", query: "Mexican restaurant" },
];

const NEEDS: { key: MessageKey; emoji: string; query: string }[] = [
  { key: "dine.cheap", emoji: "💵", query: "cheap eats" },
  { key: "dine.late", emoji: "🌙", query: "late night food" },
  { key: "dine.veg", emoji: "🥗", query: "vegetarian restaurant" },
  { key: "dine.vegan", emoji: "🌱", query: "vegan restaurant" },
  { key: "dine.halal", emoji: "☪️", query: "halal restaurant" },
];

export default function DiningPage() {
  const { t, school } = usePrefs();
  return (
    <div className="page">
      <PageTitle title={school ? t("dine.title", { city: school.city }) : t("nav.dining")} />
      {!school ? <NeedSchool /> : (
        <>
          <p className="muted">{t("places.tapHint")}</p>
          <h2>{t("dine.byCuisine")}</h2>
          <div className="link-grid place-grid">
            {CUISINES.map((c) => <PlaceDropdown key={c.key} category={c.key} emoji={c.emoji} mapsHref={mapsSearch(c.query, school.city)} />)}
          </div>
          <h2 className="spaced">{t("dine.byNeed")}</h2>
          <div className="link-grid place-grid">
            {NEEDS.map((c) => <PlaceDropdown key={c.key} category={c.key} emoji={c.emoji} mapsHref={mapsSearch(c.query, school.city)} />)}
            <LinkCard href={siteSearch("dining halls", school.domain)} icon="🏫" label={t("dine.campus")}
              detail={t("res.siteNote", { domain: school.domain })} />
          </div>
        </>
      )}
    </div>
  );
}
