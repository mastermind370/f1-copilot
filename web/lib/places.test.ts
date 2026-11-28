import assert from "node:assert/strict";
import { test } from "node:test";
import { compactCount, miles, priceLabel, starSlots } from "./places.ts";

test("star slots round to the nearest half", () => {
  assert.deepEqual(starSlots(4.6), ["full", "full", "full", "full", "half"]);
  assert.deepEqual(starSlots(4.8), ["full", "full", "full", "full", "full"]);
  assert.deepEqual(starSlots(3.2), ["full", "full", "full", "empty", "empty"]);
  assert.deepEqual(starSlots(0), ["empty", "empty", "empty", "empty", "empty"]);
  assert.deepEqual(starSlots(9), ["full", "full", "full", "full", "full"]);
});

test("price level shows dollar signs, nothing when unknown or free", () => {
  assert.equal(priceLabel(2), "$$");
  assert.equal(priceLabel(null), "");
  assert.equal(priceLabel(0), "");
});

test("rating counts are compact", () => {
  assert.equal(compactCount(812, "en-US"), "812");
  assert.equal(compactCount(1530, "en-US"), "1.5K");
});

test("distances show in miles", () => {
  assert.equal(miles(0.5), "0.3 mi");
  assert.equal(miles(3.2), "2.0 mi");
  assert.equal(miles(20), "12 mi");
});
