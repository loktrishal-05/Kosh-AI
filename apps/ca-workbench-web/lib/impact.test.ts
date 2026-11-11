import test from "node:test";
import assert from "node:assert/strict";
import { impact } from "./impact.ts";

test("half the sorting done doubles an accountant's capacity and halves the owner's hours", () => {
  const r = impact({ hoursPerMonth: 18, feePerFiling: 2000, filingsPerYear: 12, shareDone: 0.5 });
  assert.deepEqual(r, { hoursSavedMonth: 9, hoursSavedYear: 108, feeAtStakeYear: 12000, accountantCapacity: 2 });
});
test("the share is clamped so nothing divides by zero", () => {
  assert.equal(impact({ hoursPerMonth: 10, feePerFiling: 1, filingsPerYear: 1, shareDone: 5 }).accountantCapacity, 10);
  assert.equal(impact({ hoursPerMonth: 10, feePerFiling: 1, filingsPerYear: 1, shareDone: -1 }).hoursSavedMonth, 0);
});
