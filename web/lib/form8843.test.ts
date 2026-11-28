import assert from "node:assert/strict";
import { test } from "node:test";
import { type Answers8843, compute8843, daysPresent, guessPriorVisas, standaloneDeadline, returnDeadline } from "./form8843.ts";

const base = (over: Partial<Answers8843> = {}): Answers8843 => ({
  taxYear: 2026, dependent: false, visa: "F-1", lastEntry: "2026-08-20", currentStatus: "F-1", statusChanged: "",
  citizenship: "India", passportCountry: "India", stays: [{ arrive: "2025-08-25", depart: null }],
  school: "Rutgers University", director: "Rutgers Global ISSS", priorVisas: {}, appliedLPR: false, lprExplain: "",
  hadUsIncome: false, ...over,
});

test("arrival and departure days both count", () => {
  assert.equal(daysPresent([{ arrive: "2026-08-01", depart: "2026-08-03" }], 2026, "2027-01-10"), 3);
});

test("a stay that started last year counts only this year's days", () => {
  assert.equal(daysPresent([{ arrive: "2025-08-25", depart: null }], 2026, "2027-01-10"), 365);
  assert.equal(daysPresent([{ arrive: "2025-08-25", depart: null }], 2025, "2027-01-10"), 129); // Aug 25–Dec 31
});

test("trips abroad are subtracted and overlaps aren't double counted", () => {
  const stays = [
    { arrive: "2025-08-25", depart: "2026-05-20" }, // home for the summer
    { arrive: "2026-08-15", depart: null },
    { arrive: "2026-08-15", depart: "2026-08-20" }, // duplicate entry
  ];
  // Jan 1–May 20 = 140 days, Aug 15–Dec 31 = 139 days
  assert.equal(daysPresent(stays, 2026, "2027-01-10"), 279);
});

test("an unfinished year stops counting today", () => {
  assert.equal(daysPresent([{ arrive: "2026-11-01", depart: null }], 2026, "2026-11-27"), 27);
});

test("leap years have 366 days", () => {
  assert.equal(daysPresent([{ arrive: "2027-12-01", depart: null }], 2028, "2029-02-01"), 366);
});

test("deadlines move off weekends", () => {
  assert.equal(standaloneDeadline(2026), "2027-06-15"); // a Tuesday
  assert.equal(standaloneDeadline(2025), "2026-06-15"); // a Monday
  assert.equal(standaloneDeadline(2024), "2025-06-16"); // June 15, 2025 is a Sunday
  assert.equal(returnDeadline(2026), "2027-04-15");
});

test("first-year student: exempt, line 4b equals this year's days, mail by June 15", () => {
  const r = compute8843(base(), "2027-01-10");
  const line = (n: string) => r.lines.find((l) => l.line === n)!;
  assert.equal(r.exempt, true);
  assert.equal(line("4a").value, "2026: 365 · 2025: 129 · 2024: 0");
  assert.equal(line("4b").value, "365");
  assert.equal(line("1a").value, "F-1, 2026-08-20");
  assert.equal(line("12").value, "No");
  assert.equal(line("3b").value, ""); // the app never handles passport numbers
  assert.deepEqual(r.mail.address, ["Department of the Treasury", "Internal Revenue Service Center", "Austin, TX 73301-0215"]);
  assert.equal(r.mail.deadline, "2027-06-15");
  assert.deepEqual(r.warnings, []);
});

test("more than 5 student years: line 12 Yes and a residency warning", () => {
  const prior = { 2020: "F", 2021: "F", 2022: "F", 2023: "F", 2024: "F", 2025: "F" } as const;
  const r = compute8843(base({ priorVisas: prior, stays: [{ arrive: "2019-08-20", depart: null }] }), "2027-01-10");
  assert.equal(r.exempt, false);
  assert.equal(r.lines.find((l) => l.line === "12")!.value, "Yes");
  assert.equal(r.lines.find((l) => l.line === "4b")!.value, "");
  assert.equal(r.warnings.length, 2);
});

test("dependents fill Part I only; income moves the deadline to April", () => {
  const r = compute8843(base({ dependent: true, hadUsIncome: true }), "2027-01-10");
  assert.ok(!r.lines.some((l) => l.line === "9"));
  assert.equal(r.mail.withReturn, true);
  assert.equal(r.mail.deadline, "2027-04-15");
});

test("line 11 is prefilled from the years you were here", () => {
  const g = guessPriorVisas([{ arrive: "2024-08-20", depart: null }], 2026);
  assert.deepEqual(g, { 2020: "", 2021: "", 2022: "", 2023: "", 2024: "F", 2025: "F" });
});
