"use client";

import type { ReactNode } from "react";
import { ExternalIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";

/** An outbound link card: icon or emoji, label, optional detail, opens in a new tab. */
export function LinkCard({ href, icon, label, detail }: { href: string; icon: ReactNode; label: string; detail?: string }) {
  return (
    <a className="link-card" href={href} target="_blank" rel="noreferrer">
      <span className="link-icon" aria-hidden="true">{icon}</span>
      <span className="link-text">
        <span className="link-label">{label}</span>
        {detail && <span className="link-detail">{detail}</span>}
      </span>
      <ExternalIcon size={16} className="link-ext" />
    </a>
  );
}

/** Shown on campus-specific pages until a school is picked. */
export function NeedSchool() {
  const { t, openPicker } = usePrefs();
  return (
    <div className="card empty-card">
      <p>{t("hub.pickFirst")}</p>
      <button type="button" className="btn" onClick={openPicker}>{t("school.choose")}</button>
    </div>
  );
}

export function PageTitle({ title, intro }: { title: string; intro?: string }) {
  return (
    <>
      <h1>{title}</h1>
      {intro && <p className="lead">{intro}</p>}
    </>
  );
}
