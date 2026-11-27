import assert from "node:assert/strict";
import { test } from "node:test";
import { compatibility, decode, encode, isComplete, QUESTIONS } from "./roommates.ts";

const all = (v: 0 | 1 | 2) => Object.fromEntries(QUESTIONS.map((q) => [q, v])) as Record<(typeof QUESTIONS)[number], 0 | 1 | 2>;

test("codes round-trip and reject junk", () => {
  const a = { ...all(1), smoke: 0 as const, budget: 2 as const };
  assert.deepEqual(decode(encode(a)), a);
  assert.equal(decode(" rm1-01210021 ")?.clean, 1);
  assert.equal(decode("RM1-0121002"), null);
  assert.equal(decode("RM1-01210023"), null);
  assert.equal(decode("hello"), null);
});

test("identical answers are 100%, opposites are 0%", () => {
  assert.equal(compatibility(all(1), all(1)).percent, 100);
  assert.equal(compatibility(all(0), all(2)).percent, 0);
});

test("bigger, heavier differences rank first", () => {
  const a = all(0);
  const b = { ...all(0), guests: 1 as const, smoke: 2 as const };
  const r = compatibility(a, b);
  assert.deepEqual(r.differences, ["smoke", "guests"]);
  assert.ok(r.percent < 100 && r.percent > 0);
});

test("completeness", () => {
  assert.equal(isComplete({ sleep: 0 }), false);
  assert.equal(isComplete(all(2)), true);
});
