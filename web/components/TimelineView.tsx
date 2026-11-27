"use client";

import { usePrefs } from "@/components/Providers";
import { type FactField, formatDate, formatRange, shortLabel, type Timeline, type TimelineItem } from "@/lib/api";
import { FACT_TEXT, type MessageKey } from "@/lib/i18n";
import { type CalEvent, downloadIcs, slug } from "@/lib/ics";
import { CalendarIcon } from "@/components/Icons";

/** Calendar events for one timeline item: one event, or opens + closes for a window. */
export function itemEvents(item: TimelineItem, t: (k: MessageKey, v?: Record<string, string | number>) => string): CalEvent[] {
  const base = { description: [item.message, ...item.notes].filter(Boolean).join("\n"), url: item.source_url, remindDaysBefore: [7, 1] };
  const uid = slug(`${item.rule_id}-${item.label}`);
  if (item.kind === "window") {
    if (!item.start || !item.end) return [];
    return [
      { ...base, uid: `${uid}-open`, date: item.start, title: t("cal.opens", { label: shortLabel(item.label) }) },
      { ...base, uid: `${uid}-close`, date: item.end, title: t("cal.closes", { label: shortLabel(item.label) }) },
    ];
  }
  if ((item.kind === "deadline" || item.kind === "earliest") && item.date) return [{ ...base, uid, date: item.date, title: item.label }];
  return [];
}

function ItemCard({ item }: { item: TimelineItem }) {
  const { t, locale } = usePrefs();

  let when = "";
  if (item.kind === "window") when = formatRange(item.start, item.end, locale);
  else if (item.kind === "deadline" || item.kind === "earliest") when = formatDate(item.date, locale);
  else if (item.kind === "limit") when = `${item.value} ${item.unit}`;

  let rel: string | null = null;
  if (item.status === "active") rel = item.kind === "window" ? t("tl.openNow") : t("tl.now");
  else if (item.status === "upcoming" && item.days_until !== null)
    rel = item.days_until === 0 ? t("tl.today") : t(item.kind === "window" ? "tl.opensIn" : "tl.inDays", { n: item.days_until });

  return (
    <article className={`card item status-${item.status}`}>
      <div className="item-head">
        <div>
          <h3 lang="en">{item.label}</h3>
          {when && <div className="when">{when}</div>}
        </div>
        {rel && <span className={`pill ${item.status}`}>{rel}</span>}
      </div>
      {item.message && <p lang="en">{item.message}</p>}
      <details>
        <summary>{t("tl.how")}</summary>
        <ul className="trace">
          {item.explanation.map((step, i) => (
            <li key={i}><code>{step}</code></li>
          ))}
        </ul>
      </details>
      {item.notes.length > 0 && (
        <ul className="notes" lang="en">
          {item.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
      {item.status !== "past" && itemEvents(item, t).length > 0 && (
        <button type="button" className="btn ghost small cal-btn"
          onClick={() => downloadIcs(`${slug(item.label)}.ics`, itemEvents(item, t))}>
          <CalendarIcon size={16} /> {t("cal.add")}
        </button>
      )}
      <div className="muted small source-line">
        <a href={item.source_url} target="_blank" rel="noreferrer">
          {t("tl.source")}{item.citation ? ` (${item.citation})` : ""}
        </a>{" "}
        · {item.rule_id} v{item.rule_version} · {t("tl.verified", { date: formatDate(item.last_verified, locale) })}
        {item.verification === "secondary" && <span className="badge">{t("tl.secondary")}</span>}
      </div>
    </article>
  );
}

export default function TimelineView({ timeline, schema }: { timeline: Timeline; schema: FactField[] }) {
  const { t, lang, locale } = usePrefs();
  const label = (name: string) =>
    lang === "en"
      ? schema.find((f) => f.name === name)?.label ?? name
      : FACT_TEXT[lang]?.[name]?.[0] ?? schema.find((f) => f.name === name)?.label ?? name;

  const sections: { title: MessageKey; items: TimelineItem[] }[] = [
    { title: "tl.upcoming", items: timeline.items.filter((i) => i.status === "active" || i.status === "upcoming") },
    { title: "tl.info", items: timeline.items.filter((i) => i.status === "info") },
    { title: "tl.past", items: timeline.items.filter((i) => i.status === "past") },
  ];

  return (
    <div className="timeline">
      <p className="muted small">
        {t("tl.asOf", { date: formatDate(timeline.as_of, locale) })}
        {lang !== "en" && ` · ${t("tl.englishNote")}`}
      </p>
      {(() => {
        const all = timeline.items.filter((i) => i.status !== "past" && i.status !== "info").flatMap((i) => itemEvents(i, t));
        return all.length > 0 ? (
          <div className="cal-all">
            <button type="button" className="btn" onClick={() => downloadIcs("f1-deadlines.ics", all)}>
              <CalendarIcon size={18} /> {t("cal.addAll")}
            </button>
            <span className="muted small">{t("cal.note")}</span>
          </div>
        ) : null;
      })()}
      {timeline.items.length === 0 && <div className="card empty-card"><p>{t("tl.empty")}</p></div>}
      {sections
        .filter((s) => s.items.length)
        .map((s) => (
          <section key={s.title}>
            <h2>{t(s.title)}</h2>
            {s.items.map((item) => <ItemCard key={`${item.rule_id}-${item.label}`} item={item} />)}
          </section>
        ))}
      {timeline.needs_info.length > 0 && (
        <section className="card needs">
          <h2>{t("tl.needs")}</h2>
          <ul>
            {timeline.needs_info.map((n) => (
              <li key={n.rule_id}>
                <strong lang="en">{n.title}:</strong> {n.missing.map(label).join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}
      {timeline.stale_rules.length > 0 && (
        <div className="banner warn">{t("tl.stale", { rules: timeline.stale_rules.join(", ") })}</div>
      )}
      <p className="muted small">{t("tl.disclaimer")} {t("disclaimer")}</p>
    </div>
  );
}
