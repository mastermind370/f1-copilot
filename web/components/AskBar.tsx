"use client";

import { type FormEvent, useEffect, useState } from "react";
import { ArrowUpIcon, SparkIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";

interface Props {
  initial?: string;
  busy?: boolean;
  autoFocus?: boolean;
  onAsk: (question: string) => void;
}

export default function AskBar({ initial = "", busy = false, autoFocus = false, onAsk }: Props) {
  const { t } = usePrefs();
  const [value, setValue] = useState(initial);

  useEffect(() => setValue(initial), [initial]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (q && !busy) onAsk(q);
  }

  return (
    <form className="ask-bar" onSubmit={submit} role="search">
      <SparkIcon size={20} className="ask-spark" />
      <label htmlFor="ask-input" className="sr-only">{t("ask.placeholder")}</label>
      <input
        id="ask-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t("ask.placeholder")}
        maxLength={1000}
        autoFocus={autoFocus}
      />
      <button type="submit" className="ask-go" disabled={busy || !value.trim()} aria-label={t("ask.button")}>
        {busy ? <span className="spinner" aria-hidden="true" /> : <ArrowUpIcon size={20} />}
      </button>
    </form>
  );
}
