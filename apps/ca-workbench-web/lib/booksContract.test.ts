import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { glance, journalCsv, journalLedgerTotals, journalRows, money, statementRows } from "./booksFlow.ts";

// The fixtures are the REAL converter output (regenerate with scripts/gen_books_fixtures.py). Every screen's formatting code must cope with all of them.
const load = (n: string) => JSON.parse(readFileSync(new URL(`./fixtures/books_${n}.json`, import.meta.url), "utf8"));
const cases = [["business_textbook", "business"], ["kirana_full_year", "business"], ["gst_trader_full_year", "business"], ["nonprofit_club", "nonprofit"], ["individual_freelancer", "individual"]] as const;

for (const [name, entity] of cases) {
  test(`the results screens can render the real converter output: ${name}`, () => {
    const r = load(name);
    const cards = glance(r, entity);
    assert.ok(cards.length >= 4 && cards.every(c => /^[\d,]*₹?/.test(money(c.amount)) || money(c.amount).startsWith("₹")));
    const tables = statementRows(r.statements, entity);
    assert.equal(tables.length, name.startsWith("gst") ? 4 : 3);
    for (const t of tables) { assert.ok(t.rows.length > 0, t.key); for (const row of t.rows) assert.match(money(row.amount), /^-?₹[\d,]+\.\d{2}$/, `${t.key}/${row.label}`); }
    assert.ok(journalRows(r.journal, "all").length > 0 && journalLedgerTotals(r.journal) && journalCsv(r.journal).split("\n").length > r.journal.length);
    assert.equal(r.trial_balance.balanced && r.statements.balance_sheet.balanced && r.crosscheck.agrees, true);
  });
}

test("the headline figures on the cards are the hand-computed ones", () => {
  const amount = (n: string, e: "business" | "nonprofit" | "individual", label: RegExp) => glance(load(n), e).find(c => label.test(c.label))!.amount;
  assert.equal(amount("business_textbook", "business", /^Profit/), "211000.00");
  assert.equal(amount("nonprofit_club", "nonprofit", /^Surplus/), "10200.00");
  assert.equal(amount("individual_freelancer", "individual", /^Savings/), "128000.00");
});
