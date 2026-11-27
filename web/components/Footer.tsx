"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePrefs } from "@/components/Providers";
import { FULL_LANGS } from "@/lib/i18n";

export default function Footer() {
  const { t, lang } = usePrefs();
  if (usePathname() === "/") return null;
  return (
    <footer className="site-footer">
      <div className="wrap">
        <p className="disclaimer-text">{t("disclaimer")}</p>
        <p className="muted small">{t("footer")}</p>
        {!FULL_LANGS.includes(lang) && <p className="muted small">{t("lang.partial")}</p>}
        <nav className="footer-links" aria-label="Footer">
          <Link href="/privacy">{t("footer.privacy")}</Link>
          <a href="https://github.com/mastermind370/f1-copilot" target="_blank" rel="noreferrer">GitHub</a>
          <a href="https://github.com/mastermind370/f1-copilot/issues/new" target="_blank" rel="noreferrer">{t("footer.report")}</a>
        </nav>
      </div>
    </footer>
  );
}
