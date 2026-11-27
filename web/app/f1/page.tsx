"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AskBar from "@/components/AskBar";
import HeroArt from "@/components/HeroArt";
import {
  ArrowRightIcon,
  BriefcaseIcon,
  BuildingIcon,
  IdIcon,
  PlaneIcon,
  ReceiptIcon,
  RocketIcon,
  BookIcon,
} from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import TaxBanner from "@/components/TaxBanner";
import { api, formatDate, formatRange, shortLabel, type TimelineItem } from "@/lib/api";
import type { MessageKey } from "@/lib/i18n";
import { loadFacts } from "@/lib/storage";

const POPULAR: MessageKey[] = ["q.opt", "q.travel", "q.fee", "q.address"];

const GUIDES: { id: string; Icon: typeof BriefcaseIcon; q?: MessageKey; href?: string }[] = [
  { id: "opt", Icon: BriefcaseIcon, q: "q.opt" },
  { id: "stem", Icon: RocketIcon, q: "q.stem" },
  { id: "cpt", Icon: BookIcon, q: "q.cpt" },
  { id: "travel", Icon: PlaneIcon, q: "q.travel" },
  { id: "status", Icon: IdIcon, q: "q.status" },
  { id: "taxes", Icon: ReceiptIcon, href: "/f1/taxes" },
];

export default function F1OverviewPage() {
  const { t, locale, school, openPicker } = usePrefs();
  const router = useRouter();
  const [deadlines, setDeadlines] = useState<TimelineItem[] | null>(null);

  // If the student saved facts in this browser, preview their next deadlines.
  useEffect(() => {
    const facts = loadFacts();
    if (Object.keys(facts).length === 0) {
      setDeadlines([]);
      return;
    }
    api
      .timeline(facts)
      .then((tl) =>
        setDeadlines(
          tl.items.filter((i) => i.status === "active" || i.status === "upcoming").slice(0, 4),
        ),
      )
      .catch(() => setDeadlines([]));
  }, []);

  const ask = (q: string) => router.push(`/f1/ask?q=${encodeURIComponent(q)}`);

  return (
    <div className="home">
      <TaxBanner />
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">{t("home.eyebrow")}</p>
          <h1 className="hero-title">
            {t("home.title1")}
            <br />
            <span className="hero-accent">{t("home.title2")}</span>
          </h1>
          <p className="lead">{t("home.sub")}</p>
          <AskBar onAsk={ask} />
        </div>
        <div className="hero-visual" aria-hidden="true">
          <HeroArt />
        </div>
      </section>

      <section>
        <h2 className="eyebrow">{t("home.popular")}</h2>
        <div className="chips">
          {POPULAR.map((key) => (
            <button key={key} type="button" className="chip" onClick={() => ask(t(key))}>
              {t(key)}
            </button>
          ))}
        </div>
      </section>

      <section>
        <div className="section-head">
          <h2>{t("home.deadlines")}</h2>
          <Link href="/f1/timeline" className="see-all">
            {t("home.viewAll")} <ArrowRightIcon size={16} />
          </Link>
        </div>
        {deadlines && deadlines.length > 0 ? (
          <div className="deadline-row">
            {deadlines.map((d) => (
              <Link key={`${d.rule_id}-${d.label}`} href="/f1/timeline" className="deadline-card">
                <span className={`pill ${d.status}`}>
                  {d.status === "active"
                    ? t("tl.openNow")
                    : d.days_until === 0
                      ? t("tl.today")
                      : t(d.kind === "window" ? "tl.opensIn" : "tl.inDays", { n: d.days_until ?? 0 })}
                </span>
                <span className={`deadline-date${d.kind === "window" ? " range" : ""}`}>
                  {d.kind === "window" ? formatRange(d.start, d.end, locale) : formatDate(d.date, locale)}
                </span>
                <span className="deadline-label" lang="en">{shortLabel(d.label)}</span>
              </Link>
            ))}
          </div>
        ) : deadlines ? (
          <div className="card empty-card">
            <p>{t("home.deadlinesEmpty")}</p>
            <Link href="/f1/timeline" className="btn">{t("home.openTimeline")}</Link>
          </div>
        ) : null}
      </section>

      <section>
        <h2>{t("home.guides")}</h2>
        <div className="guide-grid">
          {GUIDES.map(({ id, Icon, q, href }) => {
            const title = t(`guide.${id}.title` as MessageKey);
            const body = t(`guide.${id}.body` as MessageKey);
            const inner = (
              <>
                <span className="guide-icon"><Icon size={22} /></span>
                <span className="guide-title">{title}</span>
                <span className="guide-body">{body}</span>
              </>
            );
            return href ? (
              <Link key={id} href={href} className="guide-card">{inner}</Link>
            ) : (
              <button key={id} type="button" className="guide-card" onClick={() => q && ask(t(q))}>
                {inner}
              </button>
            );
          })}
        </div>
      </section>

      <section className="card office-card">
        <span className="guide-icon"><BuildingIcon size={22} /></span>
        <div>
          <h2>{t("home.office")}</h2>
          {school ? (
            <>
              <p>{t("home.officeBody", { office: school.office })}</p>
              <p className="muted small">{school.name}</p>
            </>
          ) : (
            <p>{t("home.officeNone")}</p>
          )}
        </div>
        {school ? (
          <a className="btn" href={school.url} target="_blank" rel="noreferrer">{t("home.visit")}</a>
        ) : (
          <button type="button" className="btn" onClick={openPicker}>{t("school.choose")}</button>
        )}
      </section>
    </div>
  );
}
