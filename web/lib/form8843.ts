// Form 8843 helper: turns a student's answers into what to write on each line of the IRS form.
// Pure functions, unit-tested in form8843.test.ts. Nothing here leaves the browser.

export interface Stay {
  arrive: string; // YYYY-MM-DD
  depart: string | null; // null = still in the US
}

export type ExemptVisa = "F" | "J" | "M" | "Q" | "";

export interface Answers8843 {
  taxYear: number;
  dependent: boolean; // F-2 / J-2: Part I only
  visa: string; // e.g. "F-1"
  lastEntry: string; // line 1a date, from the I-94
  currentStatus: string; // line 1b
  statusChanged: string; // line 1b date of change, if any
  citizenship: string; // line 2
  passportCountry: string; // line 3a
  stays: Stay[];
  school: string; // line 9: name, address, phone
  director: string; // line 10: name, address, phone
  priorVisas: Record<number, ExemptVisa>; // line 11: visa held in each of the 6 prior years
  appliedLPR: boolean; // line 13
  lprExplain: string; // line 14
  hadUsIncome: boolean;
}

export interface Line {
  line: string;
  label: string;
  value: string;
  note?: string;
}

export interface Result8843 {
  lines: Line[];
  daysByYear: Record<number, number>;
  exempt: boolean; // F/J student within the first 5 calendar years
  studentYears: number; // calendar years as an exempt student, including the tax year
  warnings: string[];
  mail: { deadline: string; address: string[]; withReturn: boolean };
}

const DAY = 86_400_000;
const toDay = (iso: string) => Math.floor(Date.parse(`${iso}T00:00:00Z`) / DAY);
const fromDay = (d: number) => new Date(d * DAY).toISOString().slice(0, 10);

/** Days present in the US in a calendar year. Any part of a day counts, so arrival and departure days both count. */
export function daysPresent(stays: Stay[], year: number, today = new Date().toISOString().slice(0, 10)): number {
  const start = toDay(`${year}-01-01`);
  const end = Math.min(toDay(`${year}-12-31`), toDay(today));
  const ranges = stays
    .filter((s) => s.arrive)
    .map((s) => [Math.max(toDay(s.arrive), start), Math.min(s.depart ? toDay(s.depart) : end, end)] as const)
    .filter(([a, b]) => a <= b)
    .sort((x, y) => x[0] - y[0]);
  let total = 0;
  let cursor = -Infinity;
  for (const [a, b] of ranges) {
    const from = Math.max(a, cursor + 1); // overlapping trips aren't double counted
    if (b >= from) total += b - from + 1;
    cursor = Math.max(cursor, b);
  }
  return total;
}

/** The IRS deadline for a Form 8843 filed alone: June 15 of the next year, moved to Monday if it falls on a weekend. */
export function standaloneDeadline(taxYear: number): string {
  const d = new Date(Date.UTC(taxYear + 1, 5, 15));
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** The usual April 15 due date for Form 1040-NR, moved off weekends. */
export function returnDeadline(taxYear: number): string {
  const d = new Date(Date.UTC(taxYear + 1, 3, 15));
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export function priorYears(taxYear: number): number[] {
  return [6, 5, 4, 3, 2, 1].map((n) => taxYear - n);
}

export const IRS_ADDRESS = ["Department of the Treasury", "Internal Revenue Service Center", "Austin, TX 73301-0215"];

export function compute8843(a: Answers8843, today?: string): Result8843 {
  const y = a.taxYear;
  const daysByYear = { [y]: daysPresent(a.stays, y, today), [y - 1]: daysPresent(a.stays, y - 1, today), [y - 2]: daysPresent(a.stays, y - 2, today) };
  const prior = priorYears(y);
  const priorStudentYears = prior.filter((yr) => a.priorVisas[yr] === "F" || a.priorVisas[yr] === "J" || a.priorVisas[yr] === "M" || a.priorVisas[yr] === "Q").length;
  // Earlier years than the six on line 11 can matter too, but the form only asks about these.
  const studentYears = priorStudentYears + (daysByYear[y] > 0 ? 1 : 0);
  const exempt = !a.dependent ? studentYears <= 5 : true;
  const warnings: string[] = [];
  const lines: Line[] = [];
  const entry = a.lastEntry ? `${a.visa || "F-1"}, ${a.lastEntry}` : "";

  lines.push({ line: "1a", label: "Type of U.S. visa and date you entered the United States", value: entry,
    note: "Use your most recent entry from your I-94 record." });
  lines.push({ line: "1b", label: "Current nonimmigrant status and date of change",
    value: a.statusChanged ? `${a.currentStatus}, changed ${a.statusChanged}` : a.currentStatus || a.visa });
  lines.push({ line: "2", label: "Country of citizenship", value: a.citizenship });
  lines.push({ line: "3a", label: "Country that issued your passport", value: a.passportCountry || a.citizenship });
  lines.push({ line: "3b", label: "Passport number", value: "", note: "Write it from your passport. This app never asks for it." });
  lines.push({ line: "4a", label: `Days present in the United States in ${y}, ${y - 1} and ${y - 2}`,
    value: `${y}: ${daysByYear[y]} · ${y - 1}: ${daysByYear[y - 1]} · ${y - 2}: ${daysByYear[y - 2]}` });
  lines.push({ line: "4b", label: `Days in ${y} you claim as an exempt individual`, value: exempt ? String(daysByYear[y]) : "",
    note: exempt ? "Same as your " + y + " days on line 4a." : "Leave for a tax professional to decide; see the warning." });

  if (!a.dependent) {
    lines.push({ line: "9", label: "Academic institution you attended: name, address, phone", value: a.school });
    lines.push({ line: "10", label: "Director of your academic program: name, address, phone", value: a.director,
      note: "Many schools ask you to list the international student office here. Check your school's 8843 instructions." });
    lines.push({ line: "11", label: `Type of U.S. visa you held in ${prior[0]}–${prior[5]}`,
      value: prior.map((yr) => `${yr}: ${a.priorVisas[yr] || "—"}`).join(" · "),
      note: "Only list years you were in the U.S. Leave the others blank." });
    lines.push({ line: "12", label: "Present as a teacher, trainee or student for any part of more than 5 calendar years?",
      value: priorStudentYears > 5 ? "Yes" : "No" });
    lines.push({ line: "13", label: "Applied for, or taken steps toward, permanent residence during the year?", value: a.appliedLPR ? "Yes" : "No" });
    if (a.appliedLPR) lines.push({ line: "14", label: "Explain", value: a.lprExplain });
  }

  if (!a.dependent && !exempt) {
    warnings.push(`You've been a student in the U.S. for more than 5 calendar years (${studentYears} counting ${y}). You may be a resident for tax purposes and might not need Form 8843. Talk to your international office or a tax professional before filing.`);
  }
  if (priorStudentYears > 5) {
    warnings.push("Because line 12 is Yes, the IRS asks you to attach a statement showing you don't intend to live in the U.S. permanently.");
  }
  if (a.appliedLPR) {
    warnings.push("Because line 13 is Yes, you may not qualify as an exempt individual. Talk to a tax professional before filing.");
  }
  if (daysByYear[y] === 0) {
    warnings.push(`You entered no days in the U.S. for ${y}. If you weren't here at all in ${y}, you don't need to file for ${y}.`);
  }
  const withReturn = a.hadUsIncome;
  return {
    lines, daysByYear, exempt, studentYears, warnings,
    mail: { deadline: withReturn ? returnDeadline(y) : standaloneDeadline(y), address: IRS_ADDRESS, withReturn },
  };
}

/** Prefill line 11: years from the first arrival onward are marked F. */
export function guessPriorVisas(stays: Stay[], taxYear: number): Record<number, ExemptVisa> {
  const firstYear = Math.min(...stays.filter((s) => s.arrive).map((s) => Number(s.arrive.slice(0, 4))));
  const out: Record<number, ExemptVisa> = {};
  for (const yr of priorYears(taxYear)) {
    out[yr] = Number.isFinite(firstYear) && yr >= firstYear && daysPresent(stays, yr) > 0 ? "F" : "";
  }
  return out;
}

export function defaultTaxYear(now = new Date()): number {
  return now.getFullYear() - 1;
}

export const _test = { toDay, fromDay };
