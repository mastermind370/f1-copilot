"use client";

import { useEffect, useState } from "react";
import { usePrefs } from "@/components/Providers";
import { PageTitle } from "@/components/Resource";
import type { MessageKey } from "@/lib/i18n";
import { type Answers, compatibility, decode, encode, isComplete, QUESTIONS } from "@/lib/roommates";

const KEY = "f1copilot.roommate.v1";

export default function RoommatesPage() {
  const { t, school } = usePrefs();
  const [answers, setAnswers] = useState<Answers>({});
  const [other, setOther] = useState("");
  const [result, setResult] = useState<ReturnType<typeof compatibility> | null>(null);
  const [bad, setBad] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setAnswers(JSON.parse(raw) as Answers);
    } catch {
      /* start empty */
    }
  }, []);

  function choose(q: (typeof QUESTIONS)[number], v: 0 | 1 | 2) {
    const next = { ...answers, [q]: v };
    setAnswers(next);
    setResult(null);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* not remembered */
    }
  }

  const complete = isComplete(answers);
  const code = complete ? encode(answers) : "";
  const profileText = complete
    ? [t("rm.textHeader", { school: school?.short ?? "" }).replace(" ()", ""),
      ...QUESTIONS.map((q) => `• ${t(`rm.q.${q}` as MessageKey)} ${t(`rm.q.${q}.${answers[q]}` as MessageKey)}`),
      `${t("rm.code")}: ${code}`].join("\n")
    : "";

  async function copy(text: string, which: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard blocked: the text is still selectable */
    }
  }

  function compare() {
    const theirs = decode(other);
    setBad(!theirs);
    setResult(theirs && complete ? compatibility(answers, theirs) : null);
  }

  return (
    <div className="page">
      <PageTitle title={t("rm.title")} intro={t("rm.intro")} />
      <div className="two-col">
        <div className="quiz">
          {QUESTIONS.map((q) => (
            <fieldset key={q}>
              <legend>{t(`rm.q.${q}` as MessageKey)}</legend>
              <div className="seg">
                {([0, 1, 2] as const).map((v) => (
                  <button key={v} type="button" className={answers[q] === v ? "on" : ""} aria-pressed={answers[q] === v}
                    onClick={() => choose(q, v)}>
                    {t(`rm.q.${q}.${v}` as MessageKey)}
                  </button>
                ))}
              </div>
            </fieldset>
          ))}
        </div>

        <div>
          <section className="card">
            <h2>{t("rm.profile")}</h2>
            {!complete ? <p className="muted">{t("rm.answerAll")}</p> : (
              <>
                <pre className="profile-text">{profileText}</pre>
                <div className="row-actions">
                  <button type="button" className="btn" onClick={() => copy(profileText, "text")}>
                    {copied === "text" ? t("rm.copied") : t("rm.copyText")}
                  </button>
                  <button type="button" className="btn ghost inline" onClick={() => copy(code, "code")}>
                    {copied === "code" ? t("rm.copied") : `${t("rm.copyCode")} · ${code}`}
                  </button>
                </div>
              </>
            )}
          </section>

          <section className="card">
            <h2>{t("rm.compareTitle")}</h2>
            <p className="muted small">{t("rm.compareHint")}</p>
            <div className="inline-form">
              <input value={other} onChange={(e) => setOther(e.target.value)} placeholder="RM1-01210021" />
              <button type="button" className="btn" disabled={!complete || !other.trim()} onClick={compare}>
                {t("rm.compareBtn")}
              </button>
            </div>
            {bad && <p className="error-text">{t("rm.badCode")}</p>}
            {result && (
              <div className="match">
                <div className="match-score">{t("rm.match", { pct: result.percent })}</div>
                <div className="meter"><span style={{ width: `${result.percent}%` }} /></div>
                {result.differences.length === 0 ? <p>{t("rm.allMatch")}</p> : (
                  <>
                    <p>{t("rm.talk")}</p>
                    <ul>{result.differences.map((q) => <li key={q}>{t(`rm.q.${q}` as MessageKey)}</li>)}</ul>
                  </>
                )}
              </div>
            )}
          </section>
          <p className="banner warn small">{t("rm.safety")}</p>
        </div>
      </div>
    </div>
  );
}
