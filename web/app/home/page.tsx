"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRightIcon,
  BasketIcon,
  BowlIcon,
  BuildingIcon,
  ChatIcon,
  ChecklistIcon,
  PlaneIcon,
  SparkIcon,
  UsersIcon,
  WalletIcon,
} from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { NeedSchool } from "@/components/Resource";
import TaxBanner from "@/components/TaxBanner";
import { api, formatDate, formatRange, shortLabel, type TimelineItem } from "@/lib/api";
import type { MessageKey } from "@/lib/i18n";
import { loadFacts } from "@/lib/storage";

const TILES: { href: string; title: MessageKey; body: MessageKey; Icon: typeof SparkIcon; tone: string }[] = [
  { href: "/housing", title: "nav.housing", body: "hub.housing", Icon: BuildingIcon, tone: "tone-blue" },
  { href: "/roommates", title: "nav.roommates", body: "hub.roommates", Icon: UsersIcon, tone: "tone-violet" },
  { href: "/rides", title: "nav.rides", body: "hub.rides", Icon: PlaneIcon, tone: "tone-sky" },
  { href: "/groceries", title: "nav.groceries", body: "hub.groceries", Icon: BasketIcon, tone: "tone-green" },
  { href: "/dining", title: "nav.dining", body: "hub.dining", Icon: BowlIcon, tone: "tone-amber" },
  { href: "/community", title: "nav.community", body: "hub.community", Icon: ChatIcon, tone: "tone-teal" },
  { href: "/money", title: "nav.money", body: "hub.money", Icon: WalletIcon, tone: "tone-slate" },
  { href: "/guides", title: "nav.guides", body: "hub.guides", Icon: ChecklistIcon, tone: "tone-rose" },
];

export default function HubPage() {
  const { t, locale, school } = usePrefs();
  const [next, setNext] = useState<TimelineItem | null>(null);

  useEffect(() => {
    const facts = loadFacts();
    if (Object.keys(facts).length === 0) return;
    api
      .timeline(facts)
      .then((tl) => setNext(tl.items.find((i) => i.status === "active" || i.status === "upcoming") ?? null))
      .catch(() => setNext(null));
  }, []);

  return (
    <div className="page hub">
      <h1>{school ? t("hub.hello", { school: school.short }) : t("nav.hub")}</h1>
      {school ? <p className="lead">{t("hub.sub", { name: school.name })}</p> : <NeedSchool />}

      <TaxBanner />

      <Link href="/f1" className="f1-feature">
        <span className="f1-feature-icon"><SparkIcon size={28} /></span>
        <span className="f1-feature-text">
          <span className="f1-feature-title">F-1 Copilot</span>
          <span className="f1-feature-body">{t("hub.f1")}</span>
          {next && (
            <span className="f1-next">
              <span className={`pill ${next.status}`}>
                {next.status === "active" ? t("tl.openNow")
                  : t(next.kind === "window" ? "tl.opensIn" : "tl.inDays", { n: next.days_until ?? 0 })}
              </span>
              <span lang="en">{shortLabel(next.label)}</span>
              <strong>
                {next.kind === "window" ? formatRange(next.start, next.end, locale) : formatDate(next.date, locale)}
              </strong>
            </span>
          )}
        </span>
        <ArrowRightIcon size={22} className="f1-feature-arrow" />
      </Link>

      <div className="tile-grid">
        {TILES.map(({ href, title, body, Icon, tone }) => (
          <Link key={href} href={href} className={`tile ${tone}`}>
            <span className="tile-icon"><Icon size={24} /></span>
            <span className="tile-title">{t(title)}</span>
            <span className="tile-body">{t(body)}</span>
          </Link>
        ))}
      </div>

      {school && (
        <section className="card office-card">
          <span className="guide-icon"><BuildingIcon size={22} /></span>
          <div>
            <h2>{t("home.office")}</h2>
            <p>{t("home.officeBody", { office: school.office })}</p>
          </div>
          <a className="btn" href={school.url} target="_blank" rel="noreferrer">{t("home.visit")}</a>
        </section>
      )}
    </div>
  );
}
