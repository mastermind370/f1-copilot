"use client";

import { useEffect, useState } from "react";
import { api, type ChangeReport } from "@/lib/api";

/** Warns when official pages behind the rules have changed since they were verified. */
export default function ChangeBanner() {
  const [report, setReport] = useState<ChangeReport | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .changes()
      .then((r) => alive && setReport(r.report))
      .catch(() => {
        /* API offline: the pages show their own error */
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!report || report.rules_to_reverify.length === 0) return null;

  return (
    <div className="banner warn" role="alert">
      <strong>Some official pages changed.</strong> The sources behind these rules changed or
      couldn&apos;t be reached on {report.checked_at.slice(0, 10)}, so the dates they produce
      may be out of date until they&apos;re re-verified:{" "}
      {report.rules_to_reverify.map((f) => f.rule_id).join(", ")}. Check with your DSO.
    </div>
  );
}
