import assert from "node:assert/strict";
import { test } from "node:test";
import { docStatus, signatureExpiry } from "./documents.ts";
import { buildIcs, escapeText, fold } from "./ics.ts";
import { countUnemployment } from "./unemployment.ts";

// ---- calendar export ----------------------------------------------------------------

test("ics escapes and folds per RFC 5545", () => {
  assert.equal(escapeText("a,b;c\\d\ne"), "a\\,b\\;c\\\\d\\ne");
  const long = "X".repeat(200);
  const folded = fold(long).split("\r\n");
  assert.ok(folded.every((l) => l.length <= 75));
  assert.equal(folded.map((l, i) => (i ? l.slice(1) : l)).join(""), long);
});

test("ics builds all-day events with reminders", () => {
  const ics = buildIcs([{ uid: "opt", date: "2027-07-14", title: "OPT window closes", remindDaysBefore: [7, 1] }],
    new Date("2026-11-27T12:00:00Z"));
  assert.match(ics, /^BEGIN:VCALENDAR\r\n/);
  assert.match(ics, /DTSTART;VALUE=DATE:20270714\r\n/);
  assert.match(ics, /DTEND;VALUE=DATE:20270715\r\n/);
  assert.equal((ics.match(/BEGIN:VALARM/g) ?? []).length, 2);
  assert.match(ics, /TRIGGER:-P7D/);
  assert.ok(ics.endsWith("END:VCALENDAR\r\n"));
});

test("ics year rollover", () => {
  assert.match(buildIcs([{ uid: "x", date: "2026-12-31", title: "t" }]), /DTEND;VALUE=DATE:20270101/);
});

// ---- OPT unemployment ---------------------------------------------------------------

test("example: EAD starts July 1, job starts July 10 = 9 days used", () => {
  const r = countUnemployment({
    eadStart: "2027-07-01", stem: false, asOf: "2027-08-01",
    jobs: [{ id: "a", start: "2027-07-10", end: null, qualifies: true }],
  });
  assert.equal(r.used, 9);
  assert.equal(r.remaining, 81);
  assert.equal(r.currentlyEmployed, true);
  assert.equal(r.limitDate, null);
});

test("days between jobs count, part-time jobs don't stop the clock", () => {
  const r = countUnemployment({
    eadStart: "2027-07-01", stem: false, asOf: "2027-09-30",
    jobs: [
      { id: "a", start: "2027-07-01", end: "2027-07-31", qualifies: true },
      { id: "b", start: "2027-08-01", end: null, qualifies: false }, // under 20 hrs/week
    ],
  });
  assert.equal(r.used, 61); // Aug 1 – Sep 30
  assert.equal(r.limitDate, "2027-10-29");
});

test("STEM limit is 150 including earlier days; going over is flagged", () => {
  assert.equal(countUnemployment({ eadStart: "2027-07-01", stem: true, asOf: "2027-12-31", jobs: [] }).limit, 150);
  const over = countUnemployment({ eadStart: "2027-07-01", stem: false, asOf: "2027-10-15", jobs: [] });
  assert.equal(over.used, 107);
  assert.equal(over.status, "over");
  assert.equal(over.remaining, 0);
});

test("before the EAD start nothing counts", () => {
  const r = countUnemployment({ eadStart: "2027-07-01", stem: false, asOf: "2027-06-15", jobs: [] });
  assert.deepEqual([r.used, r.status], [0, "notStarted"]);
});

test("warning in the last 15 days", () => {
  const r = countUnemployment({ eadStart: "2027-07-01", stem: false, asOf: "2027-09-14", jobs: [] });
  assert.equal(r.used, 76);
  assert.equal(r.status, "warning");
});

// ---- documents ----------------------------------------------------------------------

test("document status thresholds", () => {
  assert.equal(docStatus(undefined, "2026-11-27").status, "missing");
  assert.deepEqual(docStatus("2026-11-26", "2026-11-27"), { status: "expired", days: -1 });
  assert.equal(docStatus("2027-02-25", "2026-11-27").status, "soon"); // 90 days
  assert.equal(docStatus("2027-02-26", "2026-11-27").status, "ok");
});

test("travel signature validity with month-end clamping", () => {
  assert.equal(signatureExpiry("2026-08-20", false), "2027-08-20");
  assert.equal(signatureExpiry("2026-08-31", true), "2027-02-28");
});

import { isTaxSeason } from "./season.ts";

test("tax season is February through April", () => {
  const months = Array.from({ length: 12 }, (_, m) => isTaxSeason(new Date(2027, m, 15)));
  assert.deepEqual(months, [false, true, true, true, false, false, false, false, false, false, false, false]);
});
