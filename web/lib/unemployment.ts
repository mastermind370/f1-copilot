// OPT unemployment day counter.
//
// Rules (Study in the States SEVIS Help Hub; 8 CFR 214.2(f)(10)(ii)(E)):
//   - Days start counting on the EAD *start date*, not the program end date.
//   - Post-completion OPT allows 90 days in total; with the STEM extension the limit is 150,
//     which includes days already used on post-completion OPT.
//   - Days are cumulative. They stop only during qualifying employment (generally at least
//     20 hours per week, related to your degree). Days abroad while unemployed still count.
// This is an estimate for planning. SEVIS keeps the official count; confirm with your DSO.

export interface Job {
  id: string;
  start: string; // YYYY-MM-DD
  end: string | null; // null = still working
  qualifies: boolean; // >= 20 hrs/week and related to your field
}

export interface UnemploymentInput {
  eadStart: string;
  stem: boolean;
  jobs: Job[];
  asOf: string;
}

export interface UnemploymentResult {
  limit: number;
  used: number;
  remaining: number;
  status: "ok" | "warning" | "over" | "notStarted";
  /** If unemployed from tomorrow on, the last day before reaching the limit. */
  limitDate: string | null;
  currentlyEmployed: boolean;
}

const DAY = 86_400_000;

export function dayNumber(iso: string): number {
  const t = Date.parse(`${iso}T00:00:00Z`);
  if (Number.isNaN(t) || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) throw new Error(`bad date: ${iso}`);
  return Math.round(t / DAY);
}

export function isoFromDay(n: number): string {
  return new Date(n * DAY).toISOString().slice(0, 10);
}

export function countUnemployment(input: UnemploymentInput): UnemploymentResult {
  const limit = input.stem ? 150 : 90;
  const start = dayNumber(input.eadStart);
  const asOf = dayNumber(input.asOf);
  if (asOf < start) {
    return { limit, used: 0, remaining: limit, status: "notStarted", limitDate: null, currentlyEmployed: false };
  }

  const covered = new Set<number>();
  let currentlyEmployed = false;
  for (const j of input.jobs) {
    if (!j.qualifies || !j.start) continue;
    const js = Math.max(dayNumber(j.start), start);
    const je = Math.min(j.end ? dayNumber(j.end) : asOf, asOf);
    for (let d = js; d <= je; d++) covered.add(d);
    if (dayNumber(j.start) <= asOf && (j.end === null || dayNumber(j.end) >= asOf)) currentlyEmployed = true;
  }

  let used = 0;
  for (let d = start; d <= asOf; d++) if (!covered.has(d)) used++;
  const remaining = Math.max(0, limit - used);
  const status = used > limit ? "over" : remaining <= 15 ? "warning" : "ok";
  const limitDate = currentlyEmployed || remaining === 0 ? null : isoFromDay(asOf + remaining);
  return { limit, used, remaining, status, limitDate, currentlyEmployed };
}
