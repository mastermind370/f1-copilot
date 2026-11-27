"use client";

import { usePrefs } from "@/components/Providers";

export default function SkipLink() {
  const { t } = usePrefs();
  return <a className="skip-link" href="#main">{t("a11y.skip")}</a>;
}
