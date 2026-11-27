"use client";

import type { FactField, FactValue, Facts } from "@/lib/api";

const GROUPS: { title: string; names: string[] }[] = [
  {
    title: "Your program",
    names: ["degree_level", "program_start_date", "program_end_date", "is_initial_student",
      "completed_one_academic_year", "full_time_cpt_months"],
  },
  {
    title: "OPT and STEM OPT",
    names: ["on_opt", "on_stem_opt", "stem_degree", "opt_ead_start_date", "opt_ead_end_date",
      "dso_recommendation_date", "stem_dso_recommendation_date"],
  },
  {
    title: "Recent events",
    names: ["last_travel_signature_date", "address_change_date", "employment_change_date"],
  },
  { title: "Taxes", names: ["tax_year", "had_us_income"] },
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
  const id = `fact-${field.name}`;
  let input;
  if (field.type === "bool") {
    input = (
      <select
        id={id}
        value={value === true ? "yes" : value === false ? "no" : ""}
        onChange={(e) =>
          onChange(field.name, e.target.value === "" ? null : e.target.value === "yes")
        }
      >
        <option value="">Not sure / skip</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    );
  } else if (field.options) {
    input = (
      <select
        id={id}
        value={typeof value === "string" ? value : ""}
        onChange={(e) => onChange(field.name, e.target.value || null)}
      >
        <option value="">Not sure / skip</option>
        {field.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
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
      <label htmlFor={id}>{field.label}</label>
      {input}
      {field.help && <span className="muted small">{field.help}</span>}
    </div>
  );
}

export default function FactsForm({ schema, facts, onChange }: Props) {
  const byName = new Map(schema.map((f) => [f.name, f]));
  const grouped = new Set(GROUPS.flatMap((g) => g.names));
  const extra = schema.filter((f) => !grouped.has(f.name)); // future facts still appear
  const groups = extra.length ? [...GROUPS, { title: "Other", names: extra.map((f) => f.name) }] : GROUPS;

  return (
    <div className="facts-form">
      {groups.map((g) => (
        <fieldset key={g.title}>
          <legend>{g.title}</legend>
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
