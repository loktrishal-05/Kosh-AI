import test from "node:test";
import assert from "node:assert/strict";
import { LAND } from "./landingText.ts";

const shape = (o: unknown): unknown => Array.isArray(o) ? o.map(() => "s") : typeof o === "object" && o ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, shape(v)])) : "s";

test("English, Hindi and Kannada have exactly the same keys and list lengths", () => {
  assert.deepEqual(shape(LAND.hi), shape(LAND.en));
  assert.deepEqual(shape(LAND.kn), shape(LAND.en));
});
test("no string is empty and the flow has the 8 steps and 3 beats everywhere", () => {
  for (const l of Object.values(LAND)) {
    assert.equal(l.steps.length, 8);
    assert.equal(l.beats.length, 3);
    assert.equal(l.proof.length, 4);
    for (const v of [l.h1a, l.h1b, l.lede, l.statement, l.closeTitle, l.foot, ...l.steps, ...l.beats]) assert.ok(v.length > 3);
  }
});
test("the proof note says these are not pilot results", () => {
  assert.match(LAND.en.proofNote, /Not pilot results/);
});
