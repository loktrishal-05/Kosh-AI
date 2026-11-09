import test from "node:test";
import assert from "node:assert/strict";
import type { Draft } from "./tallyApi.ts";
import { batchTotals, clearToken, flagMessage, getToken, paise, rupees, sampleBankCsv, setLedger, setToken } from "./tallyFlow.ts";

const draft: Draft = { vtype: "Payment", date: "2026-10-01", party: "Sharma", narration: "Rent", flags: ["NEEDS_REVIEW"], lines: [{ ledger: "Suspense A/c", side: "Dr", amount: "25000.00" }, { ledger: "Bank Account", side: "Cr", amount: "25000.00" }] };
test("every known flag has an explanation; new ledgers and unknown codes preserve names", () => {
  assert.equal(flagMessage("NEW_LEDGER:Sharma & Sons"), "First time we see Sharma & Sons; we will create it in Tally");
  for (const flag of ["GSTIN_INVALID", "GSTIN_MISSING", "ITC_BLOCKED_17_5", "GST_ASSUMED_INTRASTATE", "NEEDS_REVIEW", "SUSPICIOUS_TEXT"]) {
    assert.notEqual(flagMessage(flag), flag);
    assert.ok(flagMessage(flag).length > 30);
  }
  assert.equal(flagMessage("FUTURE_CHECK"), "FUTURE_CHECK");
});
test("setLedger renames matching lines without changing the original or other metadata", () => {
  const original = structuredClone(draft);
  const updated = setLedger(draft, "Suspense A/c", "Rent Paid");
  assert.deepEqual(draft, original);
  assert.notEqual(updated, draft);
  assert.notEqual(updated.lines, draft.lines);
  assert.equal(updated.lines[0].ledger, "Rent Paid");
  assert.deepEqual(updated.lines[1], draft.lines[1]);
  assert.deepEqual(updated.flags, draft.flags);
  assert.deepEqual(setLedger(draft, "Absent", "Rent Paid"), draft);
});
test("totals count each balanced draft once, preserve paise beyond Number range and bank directions", () => {
  const receipt: Draft = { ...draft, vtype: "Receipt", lines: [{ ledger: "Bank Account", side: "Dr", amount: "9007199254740993.01" }, { ledger: "Customer", side: "Cr", amount: "9007199254740993.01" }] };
  assert.deepEqual(batchTotals([draft, receipt]), { debit: 900719925476599301n, credit: 900719925476599301n, total: 900719925476599301n, moneyIn: 900719925474099301n, moneyOut: 2500000n });
  assert.deepEqual(batchTotals([]), { debit: 0n, credit: 0n, total: 0n, moneyIn: 0n, moneyOut: 0n });
  assert.equal(paise("0.1"), 10n);
  assert.equal(paise("25000"), 2500000n);
  for (const bad of ["NaN", "-1", "0.001", "1e3", "", "1,000.00"]) assert.throws(() => paise(bad));
});
test("rupees uses Indian grouping and exact two-digit paise for BigInt amounts", () => {
  assert.equal(rupees(11800000n), "₹1,18,000.00");
  assert.equal(rupees(900719925474099301n), "₹9,00,71,99,25,47,40,993.01");
  assert.equal(rupees(0n), "₹0.00");
  assert.equal(rupees(-101n), "-₹1.01");
});
test("sample CSV has ten synthetic data rows with the expected bank columns and mixed directions", () => {
  const [header, ...rows] = sampleBankCsv.trim().split("\n");
  assert.equal(header, "Date,Narration,Debit,Credit");
  assert.equal(rows.length, 10);
  assert.ok(rows.every(row => row.split(",").length === 4));
  for (const word of ["RENT", "SALARY", "RECEIPT", "BANK CHARGES", "ATM", "MYSTERY"]) assert.ok(sampleBankCsv.includes(word));
});
test("token helpers tolerate missing or inaccessible session storage and round-trip a token", () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
  try {
    Object.defineProperty(globalThis, "sessionStorage", { configurable: true, get() { throw new Error("Storage blocked"); } });
    assert.equal(getToken(), ""); assert.doesNotThrow(() => setToken("x")); assert.doesNotThrow(clearToken);
    Reflect.deleteProperty(globalThis, "sessionStorage");
    assert.equal(getToken(), ""); assert.doesNotThrow(() => setToken("x")); assert.doesNotThrow(clearToken);
    const items = new Map<string, string>();
    Object.defineProperty(globalThis, "sessionStorage", { configurable: true, value: { getItem: (k: string) => items.get(k), setItem: (k: string, v: string) => items.set(k, v), removeItem: (k: string) => items.delete(k) } });
    setToken("minted-token"); assert.equal(getToken(), "minted-token"); clearToken(); assert.equal(getToken(), "");
  } finally { if (descriptor) Object.defineProperty(globalThis, "sessionStorage", descriptor); else Reflect.deleteProperty(globalThis, "sessionStorage"); }
});
