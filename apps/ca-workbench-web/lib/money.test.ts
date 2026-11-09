import test from "node:test";
import assert from "node:assert/strict";
import { decimalPaise, formatMoney } from "./money.ts";

test("Indian grouping and exact paise, including safe integer boundary", () => {
  assert.equal(formatMoney(11800000), "₹1,18,000.00");
  assert.equal(formatMoney(1), "₹0.01");
  assert.equal(formatMoney(-101), "-₹1.01");
  assert.equal(formatMoney(Number.MAX_SAFE_INTEGER), "₹9,00,71,99,25,47,409.91");
  assert.equal(decimalPaise(-101), "-1.01");
  assert.throws(() => formatMoney(0.5), RangeError);
  assert.throws(() => formatMoney(Number.MAX_SAFE_INTEGER + 1), RangeError);
});
