"use client";

import { usePrefs } from "@/components/Providers";
import PlaceDropdown from "@/components/PlaceDropdown";
import { NeedSchool, PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { mapsSearch } from "@/lib/links";

// The search query stays in English so Google Maps matches store categories reliably.
const STORES: { key: MessageKey; emoji: string; query: string }[] = [
  { key: "groc.southasian", emoji: "🍛", query: "Indian grocery store" },
  { key: "groc.chinese", emoji: "🥟", query: "Chinese supermarket" },
  { key: "groc.korean", emoji: "🥢", query: "Korean grocery store" },
  { key: "groc.japanese", emoji: "🍙", query: "Japanese grocery store" },
  { key: "groc.sea", emoji: "🍜", query: "Southeast Asian grocery store" },
  { key: "groc.asianmarket", emoji: "🛒", query: "Asian supermarket" },
  { key: "groc.mideast", emoji: "🫓", query: "Middle Eastern grocery store" },
  { key: "groc.african", emoji: "🌶️", query: "African grocery store" },
  { key: "groc.latin", emoji: "🌮", query: "Latin American grocery store" },
  { key: "groc.halal", emoji: "🥩", query: "halal meat market" },
  { key: "groc.kosher", emoji: "🍞", query: "kosher grocery" },
  { key: "groc.international", emoji: "🌍", query: "international grocery store" },
];

export default function GroceriesPage() {
  const { t, school } = usePrefs();
  return (
    <div className="page">
      <PageTitle title={school ? t("groc.title", { city: school.city }) : t("nav.groceries")} intro={t("places.tapHint")} />
      {!school ? <NeedSchool /> : (
        <>
          <div className="link-grid place-grid">
            {STORES.map((s) => (
              <PlaceDropdown key={s.key} category={s.key} emoji={s.emoji} mapsHref={mapsSearch(s.query, school.city)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
