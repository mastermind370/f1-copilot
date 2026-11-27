"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BuildingIcon,
  ChecklistIcon,
  HomeIcon,
  PlaneIcon,
  SparkIcon,
  UsersIcon,
  BasketIcon,
  BowlIcon,
  ChatIcon,
  WalletIcon,
  GlobeIcon,
} from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { type Lang, LANGS, type MessageKey } from "@/lib/i18n";

const TABS: { href: string; key: MessageKey; Icon: typeof HomeIcon }[] = [
  { href: "/home", key: "nav.hub", Icon: HomeIcon },
  { href: "/f1", key: "nav.f1", Icon: SparkIcon },
  { href: "/housing", key: "nav.housing", Icon: BuildingIcon },
  { href: "/roommates", key: "nav.roommates", Icon: UsersIcon },
  { href: "/rides", key: "nav.rides", Icon: PlaneIcon },
  { href: "/groceries", key: "nav.groceries", Icon: BasketIcon },
  { href: "/dining", key: "nav.dining", Icon: BowlIcon },
  { href: "/community", key: "nav.community", Icon: ChatIcon },
  { href: "/money", key: "nav.money", Icon: WalletIcon },
  { href: "/guides", key: "nav.guides", Icon: ChecklistIcon },
];

export function LangSwitch() {
  const { lang, setLang, t } = usePrefs();
  return (
    <label className="lang-switch">
      <GlobeIcon size={16} />
      <span className="sr-only">{t("lang.label")}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label={t("lang.label")}>
        {LANGS.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>{l.label}</option>
        ))}
      </select>
    </label>
  );
}

export default function Header() {
  const pathname = usePathname();
  const { t, school, openPicker } = usePrefs();

  if (pathname === "/") return null; // the welcome screen is full-bleed

  return (
    <header className="site-header">
      <div className="wrap header-row">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">F-1</span>
          <span className="brand-name">Copilot</span>
        </Link>
        <div className="header-actions">
          <LangSwitch />
          <button type="button" className="school-btn" onClick={openPicker}>
            {school ? (
              <>
                <span className="mono small-mono">{school.mono}</span>
                {school.short}
              </>
            ) : (
              t("school.choose")
            )}
          </button>
        </div>
      </div>
      <nav className="wrap tab-bar" aria-label="Main">
        {TABS.map(({ href, key, Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link key={href} href={href} className={`nav-item${active ? " active" : ""}${href === "/f1" ? " featured" : ""}`}
              aria-current={active ? "page" : undefined}>
              <Icon size={20} />
              <span>{t(key)}</span>
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
