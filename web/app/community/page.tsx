"use client";

import { useEffect, useState } from "react";
import { ChatIcon, GlobeIcon, MapPinIcon, UsersIcon } from "@/components/Icons";
import PlatformIcon from "@/components/PlatformIcon";
import { usePrefs } from "@/components/Providers";
import { LinkCard, NeedSchool, PageTitle } from "@/components/Resource";
import { formatDate } from "@/lib/api";
import { type Community, type CommunityFile, daysSince, PLATFORMS, WECHAT_QR_DAYS } from "@/lib/communities";
import type { MessageKey } from "@/lib/i18n";
import { mapsSearch, siteSearch } from "@/lib/links";
import { todayIso } from "@/lib/local";
import data from "@/data/communities.json";

const FILE = data as CommunityFile;
const REPO = "https://github.com/mastermind370/f1-copilot/issues/new";

const WORSHIP: { key: MessageKey; q: string }[] = [
  { key: "com.w.mosque", q: "mosque" },
  { key: "com.w.hindu", q: "hindu temple" },
  { key: "com.w.gurdwara", q: "gurdwara" },
  { key: "com.w.buddhist", q: "buddhist temple" },
  { key: "com.w.church", q: "church" },
  { key: "com.w.chinesechurch", q: "chinese church" },
  { key: "com.w.koreanchurch", q: "korean church" },
  { key: "com.w.synagogue", q: "synagogue" },
  { key: "com.w.jain", q: "jain temple" },
];

function issueUrl(title: string, body: string): string {
  return `${REPO}?${new URLSearchParams({ title, body, labels: "community" }).toString()}`;
}

function GroupCard({ c, school }: { c: Community; school: string }) {
  const { t, locale } = usePrefs();
  const [today, setToday] = useState("");
  useEffect(() => setToday(todayIso()), []);
  const p = PLATFORMS[c.platform];
  const qrOld = c.platform === "wechat" && today && daysSince(c.verified, today) > WECHAT_QR_DAYS;
  return (
    <article className="card group-card">
      <div className="group-head">
        <PlatformIcon platform={c.platform} />
        <div>
          <h3>{c.name}</h3>
          <p className="muted small">
            {p.label} · {t("com.owner", { owner: c.owner })} · {t("com.verified", { date: formatDate(c.verified, locale) })}
          </p>
        </div>
      </div>
      {c.platform === "wechat" && c.qr ? (
        <figure className="qr">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={c.qr} alt={`${t("com.scan")}: ${c.name}`} width={180} height={180} />
          <figcaption className="muted small">{t("com.scan")}. {t("com.qrExpires")}</figcaption>
          {qrOld && <p className="banner warn small">{t("com.qrExpires")}</p>}
        </figure>
      ) : (
        c.url && <a className="btn" href={c.url} target="_blank" rel="noreferrer noopener">{t("com.join")} · {p.label}</a>
      )}
      <a className="report-link small" target="_blank" rel="noreferrer"
        href={issueUrl(`Report group: ${c.name} (${school})`, `Group: ${c.name}\nPlatform: ${p.label}\nWhat's wrong: `)}>
        {t("com.report")}
      </a>
    </article>
  );
}

export default function CommunityPage() {
  const { t, school } = usePrefs();
  if (!school) return <div className="page"><PageTitle title={t("nav.community")} /><NeedSchool /></div>;
  const groups = FILE.schools[school.id] ?? [];
  return (
    <div className="page">
      <PageTitle title={t("com.title", { school: school.short })} intro={t("com.intro")} />

      <section aria-labelledby="groups-h">
        <h2 id="groups-h">{t("com.groups")}</h2>
        {groups.length === 0 ? (
          <div className="card empty-card">
            <p>{t("com.groupsEmpty", { school: school.short })}</p>
          </div>
        ) : (
          <div className="group-grid">{groups.map((c) => <GroupCard key={c.name} c={c} school={school.id} />)}</div>
        )}
        <a className="btn ghost" target="_blank" rel="noreferrer"
          href={issueUrl(`Add group for ${school.short}`, `School: ${school.name}\nGroup name:\nPlatform (GroupMe, WhatsApp, Discord, Telegram, Slack, WeChat):\nInvite link:\nWho runs it (organization or officer):\nHow we can verify it:`)}>
          {t("com.submit")}
        </a>
      </section>

      <section className="card safety" aria-labelledby="safety-h">
        <h2 id="safety-h">{t("com.safetyTitle")}</h2>
        <ul>
          <li>{t("com.safety1")}</li>
          <li>{t("com.safety2")}</li>
          <li>{t("com.safety3")}</li>
        </ul>
      </section>

      <section aria-labelledby="orgs-h">
        <h2 id="orgs-h">{t("com.orgs")}</h2>
        <div className="link-grid">
          <LinkCard href={siteSearch("country student association", school.domain)} icon={<GlobeIcon size={20} />} label={t("com.orgCountry")} detail={school.domain} />
          <LinkCard href={siteSearch("international student organization", school.domain)} icon={<UsersIcon size={20} />} label={t("com.orgIntl")} detail={school.domain} />
          <LinkCard href={siteSearch("international student peer mentor buddy program", school.domain)} icon={<ChatIcon size={20} />} label={t("com.buddy")} detail={school.office} />
        </div>
      </section>

      <section aria-labelledby="worship-h">
        <h2 id="worship-h">{t("com.worship")}</h2>
        <div className="link-grid">
          {WORSHIP.map((w) => (
            <LinkCard key={w.q} href={mapsSearch(w.q, school.city)} icon={<MapPinIcon size={20} />} label={t(w.key)} detail={school.city} />
          ))}
        </div>
      </section>
    </div>
  );
}
