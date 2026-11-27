"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ReceiptIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import { isTaxSeason } from "@/lib/season";

/** Shown on the hub and F-1 overview from February through April. */
export default function TaxBanner() {
  const { t } = usePrefs();
  const [on, setOn] = useState(false);
  useEffect(() => setOn(isTaxSeason(new Date())), []); // client clock, avoids hydration mismatch
  if (!on) return null;
  return (
    <div className="banner tax-banner" role="note">
      <ReceiptIcon size={20} />
      <span>{t("tax.season")}</span>
      <Link href="/f1/taxes">{t("tax.seasonLink")}</Link>
    </div>
  );
}
