# Books from your notebook: single entry to double entry

Code: `taxsetu_engine/single_entry.py` (+ `se_rules.py`), API `taxsetu_api/books_routes.py`, UI `apps/ca-workbench-web/app/books`.
Everything is deterministic Python `Decimal`; no AI is involved in the accounting. A practising CA must review the output before it is relied on.

## Why conversion is needed
A cash book records only money in and money out. It does not record credit sales, credit purchases, stock, what is owed or owned, expenses not yet paid, or depreciation.
Those must be **derived** from year-end figures the owner can give (what customers owe, what is owed to suppliers, unsold stock) and posted as proper journal entries.

## Method (business)
1. **Opening statement of affairs.** Opening assets less liabilities give the opening capital (unless supplied). Posted as one journal.
2. **Each cash-book line is classified** by keyword rules (or the `hint` column) into a category and posted as a balanced journal: cash sale, debtor receipt, capital introduced,
   loan received/repaid, asset sale/purchase, drawings, creditor payment, cash purchase, expense head, income head, or a bank-cash contra. Unclear lines become `Other Expenses`
   or `Cash sale` with `NEEDS_REVIEW` and a question; nothing is guessed silently. A contra listed in both the cash and the bank book is posted once.
3. **Credit sales and purchases (conversion method).**
   `credit sales = closing debtors + cash received from debtors + discount allowed + bad debts + sales returns - opening debtors`
   `credit purchases = closing creditors + cash paid to creditors + discount received + purchase returns - opening creditors`
   Posted as Dr Debtors / Cr Sales and Dr Purchases / Cr Creditors. A negative result is not posted; it becomes a question ("the figures are inconsistent").
4. **Year-end adjustments.** Outstanding and prepaid expenses, accrued and advance income, depreciation. The opening side balances are reversed against their heads so each head
   carries only this period's figure.
5. **Closing.** Opening and closing stock through the Trading account, purchases and sales closed to it, gross profit to Profit and Loss, expenses and incomes closed,
   net profit and drawings to Capital. The post-closing ledgers give the Balance Sheet.

**Clubs and charities** have no Trading account: incomes and expenses close to Income and Expenditure, the surplus goes to the Capital Fund, and corpus donations go
straight to the fund. A **Receipts and Payments** account is built from the cash book alone (cash basis) and its closing cash and bank must equal the ledgers.
**Individuals** get income and expense heads, savings, and net worth at cost and at market value (the difference is shown as an unrealised gain, not income).

## GST (businesses)
Give a line a `gst_rate` (0, 0.25, 1, 1.5, 3, 5, 12, 18 or 28) and its amount is read as **including** GST: `value = amount x 100 / (100 + rate)`, rounded to the paisa, and the rest is tax.
Sales-type receipts credit **Output GST**; purchases, expenses and assets debit **Input GST**; tax never reaches profit. "GST paid to government" lines debit Output GST and
"GST refund" lines credit Input GST. For credit sales and purchases that never touch the cash book, give one `credit_sales_gst_rate` / `credit_purchases_gst_rate` in the
year-end figures (the derived total is split the same way); if your lines carry GST and a credit rate is missing, the books ask. At the end of the period input credit is
**set off** against output tax, and a GST statement shows tax collected, credit claimed, paid, refunded, still payable, and any credit carried forward (carried into the next period on rollover).
Not modelled: GST on discounts, bad debts and returns, reverse charge, composition scheme, mixed rates inside one credit total, HSN/invoice-level returns (GSTR-1/3B filing is not done here).
GST is kept for businesses; a rate on an individual's or club's line is ignored with a warning.

## Selling an asset
Give the sale line the asset's `book_value` (cost less depreciation). Profit or loss on sale = price (without GST) minus book value, posted as **Profit on Sale of Asset** (income)
or **Loss on Sale of Asset** (expense) so Fixed Assets leaves the books at its book value. Without a book value the sale is treated at book value and the books ask for it.
If you give a depreciation *rate*, assets sold are left out of its base (depreciation up to the date of sale is not computed: give an amount).

## The checks
* Every journal: debits equal credits. Adjusted trial balance: debits equal credits. Balance sheet: assets equal liabilities plus capital.
* **Independent cross-check.** Closing net worth is recomputed directly from the cash book and the year-end figures, without reading the journal, and the profit implied by the
  change in net worth must equal the Profit and Loss figure to the paisa.
* Inputs are never trusted: bad dates, negative or non-numeric amounts, lines outside the period and unknown entity types are reported in `errors` / `warnings`, never raised.
* Blank spreadsheet cells mean zero. Amounts may contain commas.

## Keeping books over time
`se_books` and `se_entries` (migration `0005_books.sql`, row-level security, no DELETE grant). A correction **voids** a line with a reason; a **closed** period is frozen
(checked inside the same transaction as the write) and stores a snapshot of its reports; **rollover** creates the next period with the closing balances as opening
(`carry_forward`), once. The audit chain records creation, setup changes, entries added, voids, close, rollover and Tally staging.
Note the reversal method: in a new period, last year's outstanding expense shows as a credit until it is paid or carried forward again; set it as still outstanding to net it off.

## Export to Tally
`to_tally` produces ledger masters (mapped to Tally groups) and balanced vouchers: cash-book lines become Receipt/Payment/Contra; the opening balances, derived entries and
adjustments become Journal vouchers. Closing entries are not exported (Tally makes its own P&L). Staged vouchers carry `REMOTEID`s so a re-send alters rather than duplicates.
The two GST ledgers are filed under `Duties & Taxes` (not yet exercised against a real Tally). Real TallyPrime 7.2 refuses ordinary vouchers on a `Stock-in-Hand` ledger, so the stock ledger is filed under `Current Assets`.

## Verification (see the README table)
Three hand-computed cases in `docs/samples/single_entry/`; `scripts/single_entry_sim.py` (a year in a shop whose true figures only the simulator knows) feeding 30 seeds
into `tests/unit/test_single_entry_acceptance.py`; 600 randomised books in `tests/unit/test_single_entry.py`; `scripts/books_e2e.py` against production;
`scripts/books_tally_verify.py` against a real Tally (ledger by ledger, 0 mismatches on four examples); UI fixtures regenerated by `scripts/gen_books_fixtures.py`.

## Not covered
TDS, inventory by item, the GST items listed above, multi-currency, partnership capital/current accounts, company-law formats (Schedule III), audit trails
beyond the app's own. Depreciation is the amount or rate you supply. Education-mode Tally only.
