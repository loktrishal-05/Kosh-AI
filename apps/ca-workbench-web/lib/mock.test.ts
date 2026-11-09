import test from "node:test";
import assert from "node:assert/strict";
import { clients, generateClients } from "./mock.ts";

test("80 deterministic clients with invoice-consistent counters and statuses", () => {
  assert.deepEqual(generateClients(), clients);
  assert.equal(clients.length, 80);
  assert.equal(new Set(clients.map(c => c.id)).size, 80);
  assert.ok(clients.some(c => c.readyToFile));
  for (const c of clients) {
    assert.match(c.gstin, /^\d{2}[A-Z]{5}\d{4}[A-Z]\dZ[A-Z0-9]$/);
    assert.ok(c.invoices.length >= 5 && c.invoices.length <= 12);
    assert.equal(c.pendingVendor2b, c.invoices.filter(i => i.status === "MISSING_2B").length);
    assert.equal(c.rule37Adjustments, c.invoices.filter(i => i.rule37).length);
    assert.equal(c.rcmAdjustments, c.invoices.filter(i => i.rcm).length);
    assert.equal(c.cashShortfall, c.invoices.some(i => i.cashShortfall));
    assert.equal(c.exceptions, c.invoices.filter(i => i.status !== "EXACT").length + c.rule37Adjustments + c.rcmAdjustments + Number(c.cashShortfall));
    assert.equal(c.readyToFile, c.exceptions === 0);
    assert.equal(c.otpRequested, false);
    assert.ok(Number.isSafeInteger(c.netGstPayablePaise));
    for (const i of c.invoices) {
      assert.ok(Number.isSafeInteger(i.register.taxablePaise) && Number.isSafeInteger(i.register.taxPaise));
      if (i.status === "EXACT") assert.deepEqual(i.register, i.gstr2b);
      if (i.status === "MISSING_2B") assert.equal(i.gstr2b, null);
      if (i.status === "MISMATCH") assert.notEqual(i.register.taxPaise, i.gstr2b?.taxPaise);
      if (i.status === "FUZZY") {
        assert.equal(i.register.taxPaise, i.gstr2b?.taxPaise);
        assert.equal([...i.register.invoiceNumber].filter((char, n) => char !== i.gstr2b?.invoiceNumber[n]).length, 1);
      }
    }
  }
});
