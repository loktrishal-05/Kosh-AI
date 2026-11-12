import test from "node:test";
import assert from "node:assert/strict";
import { countUpFrame } from "./countUp.ts";

test("count-up clamps entry and completion, including reduced-motion duration", () => {
  assert.equal(countUpFrame(120, -1), 0);
  assert.equal(countUpFrame(120, 0), 0);
  assert.equal(countUpFrame(120, 325), 105);
  assert.equal(countUpFrame(120, 650), 120);
  assert.equal(countUpFrame(120, 900), 120);
  assert.equal(countUpFrame(2.5, 0, 0), 2.5);
  assert.equal(countUpFrame(0, 300), 0);
  assert.equal(countUpFrame(-20, 650), -20);
});
