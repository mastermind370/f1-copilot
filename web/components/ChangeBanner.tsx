"use client";

import { useEffect, useState } from "react";
import { usePrefs } from "@/components/Providers";
import { api, type ChangeReport, formatDate } from "@/lib/api";

/** Warns when official pages behind the rules have changed since they were verified. */
export default function ChangeBanner() {
  const { t, locale } = usePrefs();
  const [report, setReport] = useState<ChangeReport | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .changes()
      .then((r) => alive && setReport(r.report))
      .catch(() => {
        /* API offline: pages show their own error */
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!report || report.rules_to_reverify.length === 0) return null;

  return (
    <div className="banner warn" role="alert">
      <strong>{t("banner.title")}</strong>{" "}
      {t("banner.body", {
        date: formatDate(report.checked_at.slice(0, 10), locale),
        rules: report.rules_to_reverify.map((f) => f.rule_id).join(", "),
      })}
    </div>
  );
}
