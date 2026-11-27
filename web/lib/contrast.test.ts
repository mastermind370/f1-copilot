import assert from "node:assert/strict";
import { test } from "node:test";
import { contrast, mix } from "./contrast.ts";
import { DEFAULT_THEME, THEMES } from "./themes.ts";

const PAGE_BG = "#f6f4ef";
const WHITE = "#ffffff";
const AA = 4.5; // WCAG AA for normal-size text

test("contrast math matches known values", () => {
  assert.equal(Math.round(contrast("#000000", "#ffffff") * 10) / 10, 21);
  assert.equal(contrast("#777777", "#777777"), 1);
  assert.equal(mix("#000000", "#ffffff", 0.5), "#808080");
});

for (const [id, th] of Object.entries({ default: DEFAULT_THEME, ...THEMES })) {
  test(`${id}: theme colors meet WCAG AA where text sits on them`, () => {
    // White text on primary: buttons, active tabs, brand mark, F-1 feature card.
    assert.ok(contrast(WHITE, th.primary) >= AA, `${id} white on primary ${contrast(WHITE, th.primary).toFixed(2)}`);
    // Primary text on the page background: links and headings.
    assert.ok(contrast(th.primary, PAGE_BG) >= AA, `${id} primary on page ${contrast(th.primary, PAGE_BG).toFixed(2)}`);
    // Primary text on --primary-soft: pills, monograms, selected chips.
    const soft = mix(th.primary, WHITE, 0.09);
    assert.ok(contrast(th.primary, soft) >= AA, `${id} primary on soft ${contrast(th.primary, soft).toFixed(2)}`);
    // Body text on --amber-soft: tax banner, warnings.
    const amberSoft = mix(th.accent, WHITE, 0.16);
    assert.ok(contrast("#191b23", amberSoft) >= AA, `${id} text on amber-soft`);
  });
}
