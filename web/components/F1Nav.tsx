"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePrefs } from "@/components/Providers";
import type { MessageKey } from "@/lib/i18n";

const ITEMS: { href: string; key: MessageKey }[] = [
  { href: "/f1", key: "f1nav.overview" },
  { href: "/f1/ask", key: "nav.ask" },
  { href: "/f1/timeline", key: "nav.timeline" },
  { href: "/f1/documents", key: "f1nav.documents" },
  { href: "/f1/opt-days", key: "f1nav.optDays" },
  { href: "/f1/i94", key: "f1nav.i94" },
  { href: "/f1/taxes", key: "f1nav.taxes" },
  { href: "/f1/form-8843", key: "f1nav.form8843" },
  { href: "/f1/employers", key: "f1nav.employers" },
  { href: "/f1/sources", key: "nav.sources" },
];

export default function F1Nav() {
  const pathname = usePathname();
  const { t } = usePrefs();
  return (
    <nav className="subnav" aria-label="F-1 Copilot">
      {ITEMS.map(({ href, key }) => {
        const active = pathname === href;
        return (
          <Link key={href} href={href} className={active ? "on" : ""} aria-current={active ? "page" : undefined}>
            {t(key)}
          </Link>
        );
      })}
    </nav>
  );
}
