import assert from "node:assert/strict";
import { test } from "node:test";
import { approvalRate, money } from "./employers.ts";

test("salaries are compact dollars", () => {
  assert.equal(money(166400), "$166K");
  assert.equal(money(null), "—");
});

test("approval rate ignores years without petitions", () => {
  assert.equal(approvalRate({ new_approved: 95, new_denied: 5 }), 95);
  assert.equal(approvalRate({ new_approved: 0, new_denied: 0 }), null);
});
