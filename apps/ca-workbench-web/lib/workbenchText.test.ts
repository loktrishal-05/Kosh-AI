import test from "node:test";
import assert from "node:assert/strict";
import { WORKBENCH } from "./workbenchText.ts";

test("workbench English, Hindi and Kannada have the same nonempty keys", () => {
  for (const text of Object.values(WORKBENCH)) {
    assert.deepEqual(Object.keys(text).sort(), Object.keys(WORKBENCH.en).sort());
    for (const value of Object.values(text)) assert.ok(value.trim().length > 0);
  }
});
