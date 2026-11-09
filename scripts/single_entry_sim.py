"""Simulate a year in a small shop. Returns (book, truth):
  book  = what the shopkeeper actually wrote down: a cash book (money in / money out) plus year-end figures (what customers owe, what is owed to suppliers, stock).
  truth = the real sales, purchases, profit and balances, known only to the simulator (credit sales and credit purchases never appear in the cash book).
The converted books must reproduce `truth` from `book` alone. Used by the tests and to generate docs/samples/single_entry/kirana_full_year.json."""
import json
import random
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal as D


def simulate(seed: int = 7) -> tuple:
    r = random.Random(seed)
    pick = lambda lo, hi: D(r.randrange(lo, hi + 1, 100))
    O = dict(cash=D(20000), bank=D(80000), debtors=D(30000), creditors=D(50000), stock=D(150000), fixed_assets=D(100000))
    debtors, creditors, cash, bank = O["debtors"], O["creditors"], O["cash"], O["bank"]
    entries, T = [], defaultdict(D)

    def add(day, desc, receipt=0, payment=0, mode="cash", party=""):
        nonlocal cash, bank
        receipt, payment = D(receipt), D(payment)
        entries.append({"date": day.isoformat(), "description": desc, "receipt": str(receipt) if receipt else "",
                        "payment": str(payment) if payment else "", "mode": mode, "party": party})
        if mode == "cash":
            cash += receipt - payment
        else:
            bank += receipt - payment

    for m in range(12):
        y, mo = (2026, 4 + m) if 4 + m <= 12 else (2027, 4 + m - 12)
        d = lambda day: date(y, mo, day)
        cash_sales, upi_sales, credit_sales = pick(180000, 260000), pick(130000, 170000), pick(40000, 80000)
        add(d(27), "Cash sales for the month", cash_sales)
        add(d(28), "UPI and card sales received in bank", upi_sales, mode="bank")
        T["sales"] += cash_sales + upi_sales + credit_sales
        bad = D(1500) if m == 6 else D(0)
        coll = min(pick(20000, 70000), (debtors + credit_sales - bad) * D("0.9")).to_integral_value(rounding="ROUND_FLOOR")
        disc_a = (coll * D("0.005")).to_integral_value()
        add(d(20), "Received from debtors against bills", coll, mode="bank", party="Customers")
        debtors = debtors + credit_sales - coll - disc_a - bad
        T["disc_allowed"] += disc_a
        T["bad_debts"] += bad

        cash_purch, credit_purch = pick(40000, 80000), pick(100000, 180000)
        add(d(10), "Cash purchases of goods", payment=cash_purch)
        T["purchases"] += cash_purch + credit_purch
        paid = min(pick(90000, 170000), (creditors + credit_purch) * D("0.9")).to_integral_value(rounding="ROUND_FLOOR")
        disc_r = (paid * D("0.004")).to_integral_value()
        add(d(12), "Paid to suppliers against bills", payment=paid, mode="bank", party="Suppliers")
        creditors = creditors + credit_purch - paid - disc_r
        T["disc_received"] += disc_r

        add(d(5), "Shop rent paid", payment=25000, mode="bank")
        add(d(5), "Staff salaries paid", payment=60000, mode="bank")
        add(d(15), "Transport and freight charges", payment=(t := pick(4000, 9000)))
        add(d(15), "Office expenses", payment=(o := pick(1000, 3000)))
        add(d(18), "Bank charges", payment=250, mode="bank")
        add(d(19), "Withdrawn by owner for household use", payment=40000)
        T["drawings"] += 40000
        T["expenses"] += 25000 + 60000 + t + o + 250
        if m < 11:
            e = pick(3000, 7000)
            add(d(14), "Electricity bill paid", payment=e)
            T["expenses"] += e
        else:
            T["expenses"] += 6000                      # March electricity is unpaid at year end -> outstanding
        add(d(22), "Cash deposited into bank", payment=60000)
        add(d(22), "Cash deposited into bank", receipt=60000, mode="bank")
        if m == 2:
            add(d(3), "Capital introduced by owner", 50000, mode="bank")
            T["capital_introduced"] += 50000
        if m == 4:
            add(d(9), "Purchase of furniture for shop", payment=35000, mode="bank")
            T["asset_purchases"] += 35000
        if m == 5:
            add(d(6), "Loan received from bank", 100000, mode="bank")
        if m >= 6:
            add(d(7), "Repayment of loan instalment", payment=8000, mode="bank")
            add(d(7), "Interest on loan paid", payment=1000, mode="bank")
            T["expenses"] += 1000
        assert cash >= 0 and bank >= 0, f"simulator produced a negative balance (seed {seed}, month {m})"

    closing_stock = pick(140000, 200000)
    dep = D("13500")                                   # 10% of (100,000 + 35,000)
    cogs = O["stock"] + T["purchases"] - closing_stock
    gross_profit = T["sales"] - cogs
    expenses = T["expenses"] + T["disc_allowed"] + T["bad_debts"] + dep
    net_profit = gross_profit + T["disc_received"] - expenses
    opening_capital = sum(O.values()) - O["creditors"] - O["cash"] * 0 - 0                    # placeholder, fixed below
    opening_capital = O["cash"] + O["bank"] + O["debtors"] + O["stock"] + O["fixed_assets"] - O["creditors"]
    closing_capital = opening_capital + T["capital_introduced"] + net_profit - T["drawings"]
    fixed_closing = O["fixed_assets"] + T["asset_purchases"] - dep
    assets = cash + bank + debtors + closing_stock + fixed_closing
    liabilities = creditors + D(6000) + D(52000)
    assert assets == liabilities + closing_capital, f"simulator is internally inconsistent: {assets} != {liabilities + closing_capital}"
    book = {"entity_type": "business", "name": f"Simulated Kirana Store (seed {seed})", "period_start": "2026-04-01", "period_end": "2027-03-31",
            "opening": {k: str(v) for k, v in O.items()}, "entries": sorted(entries, key=lambda e: e["date"]),
            "closing": {"debtors": str(debtors), "creditors": str(creditors), "stock": str(closing_stock),
                        "discount_allowed": str(T["disc_allowed"]), "discount_received": str(T["disc_received"]), "bad_debts": str(T["bad_debts"]),
                        "outstanding_expenses": {"Electricity Charges": "6000"}, "depreciation": str(dep)}}
    truth = {"sales": T["sales"], "purchases": T["purchases"], "gross_profit": gross_profit, "net_profit": net_profit, "cash": cash, "bank": bank,
             "debtors": debtors, "creditors": creditors, "loans": D(52000), "fixed_assets": fixed_closing, "closing_stock": closing_stock,
             "total_assets": assets, "capital": closing_capital, "opening_capital": opening_capital, "drawings": T["drawings"]}
    return book, truth


if __name__ == "__main__":
    book, truth = simulate(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
    out = sys.argv[2] if len(sys.argv) > 2 else "docs/samples/single_entry/kirana_full_year.json"
    json.dump(book, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"wrote {len(book['entries'])} entries to {out}")
    print({k: str(v) for k, v in truth.items()})
