"use client";

import { useState } from "react";
import { SearchIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { SCHOOLS, type School } from "@/lib/schools";

/** Searchable school list, used by the welcome screen and the header's school picker. */
export default function SchoolGrid({ onPick, autoFocus = false }: { onPick: (s: School) => void; autoFocus?: boolean }) {
  const { school, t } = usePrefs();
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const matches = SCHOOLS.filter((s) => !q || `${s.name} ${s.short} ${s.city}`.toLowerCase().includes(q));
  const groups: { title: string; items: School[] }[] = [
    { title: t("school.bigten"), items: matches.filter((s) => s.group === "bigten") },
    { title: t("school.other"), items: matches.filter((s) => s.group === "other") },
  ];

  return (
    <div className="school-picker-body">
      <label className="search-field">
        <SearchIcon size={18} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("school.search")}
          autoFocus={autoFocus} />
      </label>
      {matches.length === 0 && <p className="muted">{t("school.none")}</p>}
      {groups
        .filter((g) => g.items.length)
        .map((g) => (
          <section key={g.title} className="school-group">
            <h3 className="eyebrow">{g.title}</h3>
            <div className="school-grid">
              {g.items.map((s) => (
                <button key={s.id} type="button" className={`school-option${school?.id === s.id ? " selected" : ""}`}
                  onClick={() => onPick(s)}>
                  <span className="mono">{s.mono}</span>
                  <span>
                    <span className="school-name">{s.short}</span>
                    <span className="school-sub">{s.name}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}
