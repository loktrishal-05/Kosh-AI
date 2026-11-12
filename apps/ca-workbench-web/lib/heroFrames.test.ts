import test from "node:test";
import assert from "node:assert/strict";
import { FRAME_COUNT, bump, frameAt, frameUrl, loadFrame, nearestLoaded } from "./heroFrames.ts";

test("frame loading settles on success, error and timeout and clears its handlers", async t => {
  class Frame {
    decoding = ""; src = ""; complete = false; naturalWidth = 0;
    onload: (() => void) | null = null; onerror: (() => void) | null = null;
    constructor() { images.push(this); }
  }
  const images: Frame[] = [], original = Object.getOwnPropertyDescriptor(globalThis, "Image");
  Object.defineProperty(globalThis, "Image", { configurable: true, value: Frame });
  t.mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const success = loadFrame(0), first = images[0];
    assert.equal(first.src, "/hero/f_001.webp");
    first.complete = true; first.naturalWidth = 1280; first.onload!();
    assert.equal(await success, first);
    const failure = loadFrame(1); images[1].onerror!();
    assert.equal(await failure, undefined);
    const stalled = loadFrame(2); t.mock.timers.tick(8000);
    assert.equal(await stalled, undefined);
    for (const im of images) { assert.equal(im.onload, null); assert.equal(im.onerror, null); }
  } finally {
    t.mock.timers.reset();
    if (original) Object.defineProperty(globalThis, "Image", original); else Reflect.deleteProperty(globalThis, "Image");
  }
});

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
