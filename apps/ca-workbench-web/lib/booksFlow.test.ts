import test from "node:test";
import assert from "node:assert/strict";
import { bookToForm, defaultPeriod, entriesTotals, explainSource, formToBook, glance, journalCsv, journalLedgerTotals, journalRows, statementRows, type BooksForm } from "./booksFlow.ts";
import type { JournalItem } from "./booksApi.ts";
const form: BooksForm = { name: "Shop", entity_type: "business", period_start: "2026-04-01", period_end: "2027-03-31", opening: { cash: "1,00,000.01", bank: "", investments: "300", outstanding_expenses: [{ head: "Rent", amount: "1,200" }, { head: "", amount: "" }] }, closing: { stock: "2,000", investments_market_value: "800", depreciation: "" }, entries: [{ date: "2026-04-02", description: "Sale", receipt: "1,000.01", payment: "", mode: "cash" }] };
test("formToBook removes commas and empty figures, converts heads and only sends entity keys", () => {
  const b = formToBook(form);
  assert.deepEqual(b.opening, { cash: "100000.01", outstanding_expenses: { Rent: "1200" } });
  assert.deepEqual(b.closing, { stock: "2000" });
  assert.equal(b.entries[0].receipt, "1000.01"); assert.equal(b.entries[0].payment, "0");
  assert.deepEqual(formToBook({ ...form, entity_type: "individual" }).opening, { cash: "100000.01", investments: "300", outstanding_expenses: { Rent: "1200" } });
  assert.deepEqual(formToBook({ ...form, entity_type: "individual" }).closing, { investments_market_value: "800" });
  assert.deepEqual(formToBook({ ...form, entity_type: "nonprofit" }).closing, {});
  assert.deepEqual(formToBook(bookToForm(b)), b);
  assert.equal(form.opening.cash, "1,00,000.01");
});
test("form validation refuses malformed money, partial heads and duplicate heads", () => {
  assert.throws(() => formToBook({ ...form, opening: { cash: "1.001" } }), /amount/);
  assert.throws(() => formToBook({ ...form, opening: { accrued_income: [{ head: "Rent", amount: "" }] } }), /both/);
  assert.throws(() => formToBook({ ...form, opening: { accrued_income: [{ head: "Rent", amount: "1" }, { head: "Rent", amount: "2" }] } }), /different head/);
});
test("entriesTotals uses BigInt paise even beyond Number precision", () => {
  assert.deepEqual(entriesTotals([{ date: "2026-04-01", description: "A", receipt: "9,007,199,254,740,993.01" }, { date: "2026-04-02", description: "B", payment: "1.02" }]), { moneyIn: 900719925474099301n, moneyOut: 102n, difference: 900719925474099199n });
  assert.deepEqual(entriesTotals([]), { moneyIn: 0n, moneyOut: 0n, difference: 0n });
  assert.throws(() => entriesTotals([{ date: "", description: "", receipt: "-1" }]));
});
test("financial year defaults cover January and June", () => {
  assert.deepEqual(defaultPeriod(new Date(2026, 0, 10)), { period_start: "2025-04-01", period_end: "2026-03-31" });
  assert.deepEqual(defaultPeriod(new Date(2026, 5, 10)), { period_start: "2026-04-01", period_end: "2027-03-31" });
});
const journal: JournalItem[] = [{ date: "2026-04-01", source: "cash_book", narration: 'Paid "A, B"\nfor rent', flags: ["NEEDS_REVIEW"], lines: [{ ledger: 'Rent, "shop"', amount: "100.01", side: "Dr" }, { ledger: "Cash", amount: "100.01", side: "Cr" }] }];
test("journal CSV quotes commas, quotes and newlines and preserves exact amounts", () => {
  assert.equal(journalCsv(journal), 'date,source,narration,ledger,debit,credit\r\n2026-04-01,cash_book,"Paid ""A, B""\nfor rent","Rent, ""shop""",100.01,0\r\n2026-04-01,cash_book,"Paid ""A, B""\nfor rent",Cash,0,100.01');
  assert.equal(journalRows(journal, "cash_book").length, 2); assert.equal(journalRows(journal, "opening").length, 0);
  for (const s of ["opening", "cash_book", "derived", "adjustment", "closing"]) assert.ok(explainSource(s).length > 20);
  assert.match(explainSource("derived"), /not in your notebook/);
});
test("business glance shows profit or loss and the owner's share", () => {
  const cards = glance({ statements: { trading: { net_sales: "770000.00" }, profit_loss: { net_profit: "211000.00" }, balance_sheet: { total_assets: "354000.00", total_liabilities: "45000.00", capital: { closing: "309000.00" } } } }, "business");
  assert.deepEqual(cards.map(c => c.amount), ["770000.00", "211000.00", "354000.00", "45000.00", "309000.00"]);
  assert.equal(cards[1].label, "Profit");
  assert.deepEqual(glance({ statements: { profit_loss: { net_profit: "-5.00" } } }, "business")[1], { label: "Loss", amount: "5.00" });
});
test("club glance uses income, expenditure, surplus and closing fund", () => {
  const cards = glance({ statements: { income_expenditure: { total_income: "100000.00", total_expenditure: "89800.00", surplus: "10200.00" }, balance_sheet: { capital_fund: { closing: "102200.00" } } } }, "nonprofit");
  assert.deepEqual(cards.map(c => c.amount), ["100000.00", "89800.00", "10200.00", "102200.00"]);
});
test("individual glance distinguishes savings, net worth at cost and market", () => {
  const cards = glance({ statements: { income_expense: { total_income: "496000.00", total_expenses: "368000.00", savings: "128000.00" }, net_worth: { closing_at_cost: { net_worth: "241000.00" }, closing_at_market: { net_worth: "256000.00" } } } }, "individual");
  assert.deepEqual(cards.map(c => c.amount), ["496000.00", "368000.00", "128000.00", "241000.00", "256000.00"]);
});
test("statement tables follow entity order, flatten amounts and leave boolean checks out", () => {
  const tables = statementRows({ balance_sheet: { assets: { Cash: "10.00" }, total_assets: "10.00", balanced: true } }, "business");
  assert.deepEqual(tables.map(t => t.key), ["trading", "profit_loss", "balance_sheet"]);
  assert.deepEqual(tables[2].rows.map(r => r.amount), ["10.00", "10.00"]);
  assert.deepEqual(statementRows({}, "nonprofit").map(t => t.key), ["receipts_payments", "income_expenditure", "balance_sheet"]);
  assert.deepEqual(statementRows({}, "individual").map(t => t.key), ["income_expense", "net_worth", "balance_sheet"]);
});

test("ledger totals come from exact journal amounts and liabilities can be summed from rows", () => {
  assert.deepEqual(journalLedgerTotals(journal).get("Cash"), { debit: 0n, credit: 10001n });
  assert.deepEqual(journalLedgerTotals(journal).get('Rent, "shop"'), { debit: 10001n, credit: 0n });
  assert.equal(glance({ statements: { balance_sheet: { liabilities: { Creditors: "40000.01", Rent: "5000.00" } } } }, "business")[3].amount, "45000.01");
});
