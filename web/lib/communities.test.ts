import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { type Community, type CommunityFile, validateCommunity, validateFile } from "./communities.ts";

const ok = (c: Partial<Community>): Community => ({
  platform: "groupme", name: "Intl Students 2027", owner: "International Student Association",
  url: "https://groupme.com/join_group/123456/AbCdEf", verified: "2026-11-27", ...c,
} as Community);

test("valid links on every supported platform pass", () => {
  for (const c of [
    ok({}),
    ok({ platform: "whatsapp", url: "https://chat.whatsapp.com/AbC123xyz" }),
    ok({ platform: "discord", url: "https://discord.gg/abc-123" }),
    ok({ platform: "discord", url: "https://discord.com/invite/abc123" }),
    ok({ platform: "telegram", url: "https://t.me/rutgers_intl" }),
    ok({ platform: "slack", url: "https://join.slack.com/t/intl/shared_invite/zt-abc" }),
    ok({ platform: "wechat", url: undefined, qr: "/communities/qr/rutgers-cssa.png" }),
  ]) {
    assert.deepEqual(validateCommunity(c, "x"), [], JSON.stringify(c));
  }
});

test("unknown and look-alike domains are rejected", () => {
  for (const url of [
    "https://groupme.com.evil.example/join_group/1/a",
    "https://gr0upme.com/join_group/1/a",
    "https://bit.ly/abc",
    "http://groupme.com/join_group/1/a",
    "https://user:pass@groupme.com/join_group/1/a",
    "https://groupme.com/login",
  ]) {
    assert.ok(validateCommunity(ok({ url }), "x").length > 0, url);
  }
  assert.ok(validateCommunity(ok({ platform: "whatsapp", url: "https://wa.me/15551234567" }), "x").length > 0);
  assert.ok(validateCommunity(ok({ platform: "myspace" as never }), "x")[0].includes("unknown platform"));
});

test("required fields and WeChat rules", () => {
  assert.ok(validateCommunity(ok({ owner: " " }), "x").some((e) => e.includes("owner")));
  assert.ok(validateCommunity(ok({ verified: "last week" }), "x").some((e) => e.includes("verified")));
  assert.ok(validateCommunity(ok({ platform: "wechat" }), "x").some((e) => e.includes("no web links")));
  assert.ok(validateCommunity(ok({ platform: "wechat", url: undefined, qr: "https://evil.example/qr.png" }), "x").length > 0);
});

test("the shipped communities.json is valid", () => {
  const file = JSON.parse(readFileSync(new URL("../data/communities.json", import.meta.url), "utf8")) as CommunityFile;
  const schools = readFileSync(new URL("./schools.ts", import.meta.url), "utf8").match(/id: "([a-z-]+)"/g)!
    .map((m) => m.slice(5, -1));
  assert.deepEqual(validateFile(file, schools), []);
  assert.ok(validateFile({ version: 1, schools: { hogwarts: [] } }, schools)[0].includes("unknown school"));
});
