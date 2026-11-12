import test from "node:test";
import assert from "node:assert/strict";
import { FRAME_COUNT, bump, frameAt, frameUrl, nearestLoaded } from "./heroFrames.ts";

test("progress maps to a clamped frame index", () => {
  assert.equal(frameAt(-0.5), 0);
  assert.equal(frameAt(0), 0);
  assert.equal(frameAt(1), FRAME_COUNT - 1);
  assert.equal(frameAt(7), FRAME_COUNT - 1);
  assert.equal(frameAt(0.5), Math.round((FRAME_COUNT - 1) / 2));
});
test("frame file names are zero-padded and 1-based", () => {
  assert.equal(frameUrl(0), "/hero/f_001.webp");
  assert.equal(frameUrl(219), "/hero/f_220.webp");
});
test("a missing frame falls back to the nearest loaded one, never to nothing while any frame exists", () => {
  const loaded: unknown[] = new Array(10).fill(undefined);
  assert.equal(nearestLoaded(5, loaded), -1);
  loaded[2] = 1; loaded[8] = 1;
  assert.equal(nearestLoaded(5, loaded), 2);   // 3 away from 2, 3 away from 8: the earlier one wins
  assert.equal(nearestLoaded(7, loaded), 8);
  assert.equal(nearestLoaded(8, loaded), 8);
  assert.equal(nearestLoaded(0, loaded), 2);
});
test("beat visibility rises, holds and falls", () => {
  assert.equal(bump(0.1, 0.2, 0.3, 0.4, 0.5), 0);
  assert.equal(bump(0.25, 0.2, 0.3, 0.4, 0.5), 0.5);
  assert.equal(bump(0.35, 0.2, 0.3, 0.4, 0.5), 1);
  assert.equal(bump(0.45, 0.2, 0.3, 0.4, 0.5), 0.5);
  assert.equal(bump(0.6, 0.2, 0.3, 0.4, 0.5), 0);
});
