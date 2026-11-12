import test from "node:test";
import assert from "node:assert/strict";
import { LAND } from "./landingText.ts";

const shape = (o: unknown): unknown => Array.isArray(o) ? o.map(shape) : typeof o === "object" && o ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, shape(v)])) : "s";
const strings = (o: unknown): string[] => typeof o === "string" ? [o] : Object.values(o as object).flatMap(strings);

test("English, Hindi and Kannada have exactly the same keys and list lengths", () => {
  assert.deepEqual(shape(LAND.hi), shape(LAND.en));
  assert.deepEqual(shape(LAND.kn), shape(LAND.en));
});
test("no string is empty and the flow has the 8 steps and 3 beats everywhere", () => {
  for (const l of Object.values(LAND)) {
    assert.equal(l.steps.length, 8);
    assert.equal(l.beats.length, 3);
    assert.equal(l.proof.length, 4);
    assert.equal(l.agents.length, 5);
    for (const v of strings(l)) assert.ok(v.trim().length > 0);
    for (const agent of l.agents) assert.ok(agent.title.length > 3 && agent.body.length > 30);
  }
});
test("the proof note says these are not pilot results", () => {
  assert.match(LAND.en.proofNote, /Not pilot results/);
});
