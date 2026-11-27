"use client";

import { usePrefs } from "@/components/Providers";
import type { FactField, FactValue, Facts } from "@/lib/api";
import { FACT_TEXT, type MessageKey } from "@/lib/i18n";

const GROUPS: { title: MessageKey; names: string[] }[] = [
  {
    title: "tl.group.program",
    names: ["degree_level", "program_start_date", "program_end_date", "is_initial_student",
      "completed_one_academic_year", "full_time_cpt_months"],
  },
  {
    title: "tl.group.opt",
    names: ["on_opt", "on_stem_opt", "stem_degree", "opt_ead_start_date", "opt_ead_end_date",
      "dso_recommendation_date", "stem_dso_recommendation_date"],
  },
  {
    title: "tl.group.events",
    names: ["last_travel_signature_date", "address_change_date", "employment_change_date"],
  },
  { title: "tl.group.taxes", names: ["tax_year", "had_us_income"] },
];

interface Props {
  schema: FactField[];
  facts: Facts;
  onChange: (name: string, value: FactValue | null) => void;
}

function Field({ field, value, onChange }: {
  field: FactField;
  value: FactValue | undefined;
  onChange: Props["onChange"];
}) {
  const { t, lang } = usePrefs();
  const [label, help] = lang === "en" ? [field.label, field.help] : FACT_TEXT[lang]?.[field.name] ?? [field.label, field.help];
  const id = `fact-${field.name}`;
  let input;
  if (field.type === "bool") {
    input = (
      <div className="seg" role="radiogroup" aria-labelledby={`${id}-label`}>
        {[
          { v: null, text: t("tl.notSure") },
          { v: true, text: t("tl.yes") },
          { v: false, text: t("tl.no") },
        ].map((opt) => {
          const on = opt.v === null ? value === undefined : value === opt.v;
          return (
            <button key={String(opt.v)} type="button" role="radio" aria-checked={on}
              className={on ? "on" : ""} onClick={() => onChange(field.name, opt.v)}>
              {opt.text}
            </button>
          );
        })}
      </div>
    );
  } else if (field.options) {
    input = (
      <select id={id} value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(field.name, e.target.value || null)}>
        <option value="">{t("tl.notSure")}</option>
        {field.options.map((o) => (
          <option key={o} value={o}>{t(`degree.${o}` as MessageKey)}</option>
        ))}
      </select>
    );
  } else {
    input = (
      <input
        id={id}
        type={field.type === "date" ? "date" : field.type === "int" ? "number" : "text"}
        min={field.type === "int" ? 0 : undefined}
        value={value === undefined || typeof value === "boolean" ? "" : String(value)}
        onChange={(e) => {
          const v = e.target.value;
          if (!v) return onChange(field.name, null);
          onChange(field.name, field.type === "int" ? Number(v) : v);
        }}
      />
    );
  }
  return (
    <div className="field">
      <label htmlFor={id} id={`${id}-label`}>{label}</label>
      {input}
      {help && <span className="muted small">{help}</span>}
    </div>
  );
}

export default function FactsForm({ schema, facts, onChange }: Props) {
  const { t } = usePrefs();
  const byName = new Map(schema.map((f) => [f.name, f]));
  const grouped = new Set(GROUPS.flatMap((g) => g.names));
  const extra = schema.filter((f) => !grouped.has(f.name)); // new facts still appear
  const groups = extra.length
    ? [...GROUPS, { title: "tl.group.other" as MessageKey, names: extra.map((f) => f.name) }]
    : GROUPS;

  return (
    <div className="facts-form">
      {groups.map((g) => (
        <fieldset key={g.title}>
          <legend>{t(g.title)}</legend>
          {g.names
            .map((n) => byName.get(n))
            .filter((f): f is FactField => Boolean(f))
            .map((f) => (
              <Field key={f.name} field={f} value={facts[f.name]} onChange={onChange} />
            ))}
        </fieldset>
      ))}
    </div>
  );
}
