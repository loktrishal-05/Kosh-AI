import type { Book, Conversion, EntityType, Figures, JournalItem, NotebookEntry, Statements, StatementValue } from "./booksApi.ts";
import { paise, rupees } from "./tallyFlow.ts";
export type HeadLine = { head: string; amount: string };
export type FormFigures = Record<string, string | HeadLine[]>;
export interface BooksForm extends Omit<Book, "opening" | "closing"> { opening: FormFigures; closing: FormFigures }
export const heads = ["outstanding_expenses", "prepaid_expenses", "accrued_income", "advance_income"] as const;
const common = ["cash", "bank", "fixed_assets", "loans"];
export function figureKeys(entity: EntityType, closing = false): string[] {
  return closing ? [...(entity === "business" ? ["debtors", "creditors", "stock", "discount_allowed", "discount_received", "bad_debts", "sales_returns", "purchase_returns", "credit_sales_gst_rate", "credit_purchases_gst_rate"] : []), "depreciation", ...(entity === "individual" ? ["investments_market_value"] : []), ...heads]
    : [...common, ...(entity === "business" ? ["debtors", "creditors", "stock"] : []), ...(entity === "individual" ? ["investments"] : []), "capital", ...heads];
}
export function cleanAmount(value: string): string {
  const clean = value.replace(/,/g, "").trim();
  if (clean && !/^-?\d+(?:\.\d{1,2})?$/.test(clean)) throw new Error(`"${value}" is not an amount. Use rupees with at most two decimal places.`);
  return clean;
}
export function formToBook(form: BooksForm): Book {
  function figures(raw: FormFigures, closing: boolean): Figures {
    const out: Figures = {};
    for (const key of figureKeys(form.entity_type, closing)) {
      const value = raw[key];
      if (Array.isArray(value)) {
        if (value.length > 50) throw new Error("Use at most 50 heads in each list.");
        const pairs = value.filter(v => v.head.trim() && v.amount.trim()).map(v => [v.head.trim(), cleanAmount(v.amount)]);
        if (new Set(pairs.map(p => p[0])).size !== pairs.length) throw new Error("Use a different head name for each line, or combine their amounts.");
        if (value.some(v => !!v.head.trim() !== !!v.amount.trim())) throw new Error("Enter both a head name and its amount, or leave both blank.");
        if (pairs.length) out[key] = Object.fromEntries(pairs);
      } else if (value?.trim()) out[key] = cleanAmount(value);
    }
    return out;
  }
  return { name: form.name.trim() || "My books", entity_type: form.entity_type, period_start: form.period_start, period_end: form.period_end, opening: figures(form.opening, false), closing: figures(form.closing, true), entries: form.entries.map(e => ({ ...e, receipt: cleanAmount(e.receipt || "") || "0", payment: cleanAmount(e.payment || "") || "0" })) };
}
export function bookToForm(book: Book): BooksForm {
  const figures = (raw: Figures): FormFigures => Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, typeof v === "string" ? v : Object.entries(v).map(([head, amount]) => ({ head, amount }))]));
  return { ...book, opening: figures(book.opening), closing: figures(book.closing) };
}
export function entriesTotals(entries: readonly NotebookEntry[]) {
  let moneyIn = 0n, moneyOut = 0n;
  for (const e of entries) { moneyIn += paise(cleanAmount(e.receipt || "") || "0"); moneyOut += paise(cleanAmount(e.payment || "") || "0"); }
  return { moneyIn, moneyOut, difference: moneyIn - moneyOut };
}
export function defaultPeriod(today: Date) {
  const year = today.getMonth() < 3 ? today.getFullYear() - 1 : today.getFullYear();
  return { period_start: `${year}-04-01`, period_end: `${year + 1}-03-31` };
}
const AMOUNT = /^-?\d+(?:\.\d{1,2})?$/;
export function isAmount(value: unknown): value is string { return typeof value === "string" && AMOUNT.test(value); }
/** Indian-grouped rupees. Never throws: an unexpected value is shown as received rather than blanking the page. */
export function money(value: string): string {
  if (!isAmount(value)) return String(value ?? "");
  const negative = value.startsWith("-");
  return rupees((negative ? -1n : 1n) * paise(negative ? value.slice(1) : value));
}
export function statementAmount(statements: Statements, ...path: string[]): string {
  let v: StatementValue = statements;
  for (const key of path) { if (typeof v !== "object" || !v) return "0"; v = v[key]; }
  return typeof v === "string" ? v : "0";
}
function liabilities(statements: Statements): string {
  const total = statements.balance_sheet?.total_liabilities;
  if (typeof total === "string") return total;
  const items = statements.balance_sheet?.liabilities;
  const paiseTotal = items && typeof items === "object" ? Object.values(items).reduce<bigint>((sum, value) => sum + (typeof value === "string" ? paise(value) : 0n), 0n) : 0n;
  return `${paiseTotal / 100n}.${String(paiseTotal % 100n).padStart(2, "0")}`;
}
export function glance(result: Pick<Conversion, "statements">, entity: EntityType) {
  const s = result.statements, a = (...p: string[]) => statementAmount(s, ...p);
  const signed = (label: string, loss: string, amount: string) => ({ label: amount.startsWith("-") ? loss : label, amount: amount.replace(/^-/, "") });
  if (entity === "business") return [{ label: "Sales - goods sold", amount: a("trading", "net_sales") }, signed("Profit", "Loss", a("profit_loss", "net_profit")), { label: "What you own", amount: a("balance_sheet", "total_assets") }, { label: "What you owe", amount: liabilities(s) }, { label: "Owner’s capital - your share", amount: a("balance_sheet", "capital", "closing") }];
  if (entity === "nonprofit") return [{ label: "Income", amount: a("income_expenditure", "total_income") }, { label: "Spending", amount: a("income_expenditure", "total_expenditure") }, signed("Surplus - income left over", "Deficit - spending above income", a("income_expenditure", "surplus")), { label: "Fund - the club’s own money", amount: a("balance_sheet", "capital_fund", "closing") }];
  return [{ label: "Income", amount: a("income_expense", "total_income") }, { label: "Spending", amount: a("income_expense", "total_expenses") }, signed("Savings", "Savings shortfall", a("income_expense", "savings")), { label: "Net worth at cost - own minus owe", amount: a("net_worth", "closing_at_cost", "net_worth") }, { label: "Net worth at market - using today’s values", amount: a("net_worth", "closing_at_market", "net_worth") }];
}
export function explainSource(source: string): string {
  return ({ opening: "Where you stood at the start, turned into matching records.", cash_book: "This came from your notebook.", derived: "This was not in your notebook: we worked it out from what customers and suppliers were owed at the start and end, or from the book value of an asset you sold.", adjustment: "A year-end change for amounts due, paid early or used up.", adjustments: "A year-end change for amounts due, paid early or used up.", closing: "We moved this year’s result into your own share or fund." } as Record<string, string>)[source] || `Worked out for you (${source}).`;
}
export function journalRows(journal: readonly JournalItem[], filter = "all") {
  return journal.filter(j => filter === "all" || j.source === filter || (filter === "adjustment" && j.source === "adjustments")).flatMap(j => j.lines.map(l => ({ date: j.date, source: j.source, narration: j.narration, ledger: l.ledger, debit: l.side === "Dr" ? l.amount : "0", credit: l.side === "Cr" ? l.amount : "0" })));
}
export function journalCsv(journal: readonly JournalItem[]): string {
  const quote = (s: string) => /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  return [["date", "source", "narration", "ledger", "debit", "credit"], ...journalRows(journal).map(r => [r.date, r.source, r.narration, r.ledger, r.debit, r.credit])].map(row => row.map(quote).join(",")).join("\r\n");
}
export const statementInfo: Record<string, [string, string]> = {
  trading: ["Trading account - buying and selling goods", "What your goods earned after their purchase cost."],
  profit_loss: ["Profit and loss - income less costs", "What the business earned after everyday running costs."],
  balance_sheet: ["Balance sheet - own, owe and your share", "Where you stand at the end of this period."],
  receipts_payments: ["Receipts and payments - money in and out", "All cash and bank movements, including opening and closing money."],
  income_expenditure: ["Income and expenditure - earned and used", "The club’s income and spending belonging to this period."],
  income_expense: ["Income and expenses - earned and spent", "Your income, costs and savings for this period."],
  gst: ["GST - tax collected, paid and carried", "The tax inside your sales and purchases, what you paid the government, and what is left to pay or to claim next time."],
  net_worth: ["Net worth - what you own less what you owe", "Your own share at purchase cost and at current market values."],
};
export function plainLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\bdebtors\b/gi, "customers who owe you").replace(/\bcreditors\b/gi, "suppliers you owe")
    .replace(/\bcapital fund\b/gi, "club’s own fund").replace(/\bcapital\b/gi, "owner’s share").replace(/\bassets\b/gi, "things you own")
    .replace(/\bliabilities\b/gi, "amounts you owe").replace(/\bdrawings\b/gi, "owner’s personal withdrawals")
    .replace(/\bdepreciation\b/gi, "wear and tear of equipment").replace(/\bbad debts\b/gi, "customer bills you cannot collect")
    .replace(/\baccrued income\b/gi, "income earned but not received").replace(/\boutstanding expenses\b/gi, "costs still to pay")
    .replace(/\bprepaid expenses\b/gi, "costs paid early").replace(/\bincome received in advance\b/gi, "income received before earning it")
    .replace(/\bstock-in-trade\b/gi, "unsold goods at purchase cost").replace(/\bsuspense a\/c\b/gi, "temporary category needing your check");
}
export function statementRows(statements: Statements, entity: EntityType) {
  const keys = entity === "business" ? ["trading", "profit_loss", ...(statements.gst ? ["gst"] : []), "balance_sheet"] : entity === "nonprofit" ? ["receipts_payments", "income_expenditure", "balance_sheet"] : ["income_expense", "net_worth", "balance_sheet"];
  function flatten(value: Record<string, StatementValue>, prefix = ""): { label: string; amount: string }[] {
    return Object.entries(value).flatMap(([key, v]) => typeof v === "boolean" ? [] : typeof v === "string" ? (isAmount(v) ? [{ label: prefix + plainLabel(key), amount: v }] : []) : flatten(v, prefix + plainLabel(key) + " / "));
  }
  return keys.map(key => ({ key, title: statementInfo[key][0], caption: statementInfo[key][1], rows: flatten(statements[key] || {}) }));
}

export function journalLedgerTotals(journal: readonly JournalItem[]) {
  const totals = new Map<string, { debit: bigint; credit: bigint }>();
  for (const item of journal) for (const line of item.lines) {
    const row = totals.get(line.ledger) || { debit: 0n, credit: 0n };
    if (line.side === "Dr") row.debit += paise(line.amount); else row.credit += paise(line.amount);
    totals.set(line.ledger, row);
  }
  return totals;
}
