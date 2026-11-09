"""Synthetic cash books and the supplied textbook examples."""
import copy
import json
import random
from decimal import Decimal
from pathlib import Path

import pytest

from taxsetu_engine.single_entry import convert, parse_cash_book_csv, to_tally

D = Decimal
SAMPLES = Path(__file__).resolve().parents[2] / "docs/samples/single_entry"


def book(entity="business", entries=None, **kwargs):
    return {"entity_type": entity, "name": "Example Books", "period_start": "2026-04-01", "period_end": "2027-03-31",
            "entries": entries or [], "opening": {}, "closing": {"stock": "0"}, **kwargs}


def entry(description="", receipt="0", payment="0", mode="cash", **kwargs):
    return {"date": "2026-07-01", "description": description, "receipt": receipt, "payment": payment, "mode": mode, **kwargs}


def sample(name):
    return convert(json.loads((SAMPLES / (name + ".json")).read_text(encoding="utf-8")))


def signed_ledger(result, name):
    ledger = result["ledgers"].get(name, {"balance": "0", "side": ""})
    return D(ledger["balance"]) * (-1 if ledger["side"] == "Cr" else 1)


def check(result):
    assert not result["errors"]
    for item in result["journal"]:
        assert sum((D(l["amount"]) * (1 if l["side"] == "Dr" else -1) for l in item["lines"]), D(0)) == 0
        assert all(D(l["amount"]) > 0 and len(l["amount"].split(".")[1]) == 2 for l in item["lines"])
    assert result["trial_balance"]["balanced"]
    assert result["statements"]["balance_sheet"]["balanced"]
    assert result["crosscheck"]["agrees"]
    assert result["trial_balance"]["rows"] == sorted(result["trial_balance"]["rows"], key=lambda r: r["ledger"])
    assert [j["date"] for j in result["journal"]] == sorted(j["date"] for j in result["journal"])


def test_business_textbook():
    r = sample("business_textbook")
    check(r)
    assert not r["questions"] and r["counts"]["needs_review"] == 0
    derived = {j["narration"]: j["lines"][0]["amount"] for j in r["journal"] if j["source"] == "derived"}
    assert derived["Derived credit sales"] == "370000.00"
    assert derived["Derived credit purchases"] == "281500.00"
    assert sum(j.get("category") == "contra" for j in r["journal"]) == 1
    assert r["statements"]["trading"] == {
        "sales": "770000.00", "sales_returns": "0.00", "net_sales": "770000.00", "opening_stock": "60000.00",
        "purchases": "381500.00", "purchase_returns": "0.00", "net_purchases": "381500.00", "closing_stock": "75000.00",
        "cost_of_goods_sold": "366500.00", "gross_profit": "403500.00"}
    pl = r["statements"]["profit_loss"]
    assert pl["expenses"] == {"Rent Paid": "65000.00", "Salary and Wages": "90000.00", "Electricity Charges": "12000.00",
                               "Transport and Freight": "18000.00", "Bank Charges": "1000.00", "Discount Allowed": "3000.00",
                               "Bad Debts": "2000.00", "Depreciation": "5000.00"}
    assert (pl["total_expenses"], pl["total_other_income"], pl["net_profit"]) == ("196000.00", "3500.00", "211000.00")
    sheet = r["statements"]["balance_sheet"]
    assert sheet["assets"] == {"Cash": "13000.00", "Bank": "166000.00", "Debtors": "55000.00", "Stock-in-Trade": "75000.00", "Fixed Assets": "45000.00"}
    assert sheet["liabilities"] == {"Creditors": "40000.00", "Outstanding Expenses": "5000.00"}
    assert sheet["total_assets"] == "354000.00"
    assert sheet["capital"] == {"opening": "120000.00", "introduced": "50000.00", "net_profit": "211000.00", "drawings": "72000.00", "closing": "309000.00"}


def test_nonprofit_club():
    r = sample("nonprofit_club")
    check(r)
    assert not r["questions"]
    ie = r["statements"]["income_expenditure"]
    assert ie["income"]["Subscriptions"] == "60000.00"
    assert ie["total_income"] == "100000.00"
    assert ie["expenditure"] == {"Salaries": "37000.00", "Rent Paid": "24000.00", "Program Expenses": "15000.00",
                                  "Printing and Stationery": "4000.00", "Electricity Charges": "6000.00", "Depreciation": "3800.00"}
    assert (ie["total_expenditure"], ie["surplus"]) == ("89800.00", "10200.00")
    rp = r["statements"]["receipts_payments"]
    assert sum(map(D, rp["opening"].values())) == D("50000")
    assert sum(map(D, rp["receipts"].values())) == D("110000")
    assert sum(map(D, rp["payments"].values())) == D("93000")
    assert rp["receipts"]["Capital Fund"] == "10000.00"
    assert rp["payments"]["Fixed Assets"] == "8000.00"
    assert rp["closing"] == {"cash": "16000.00", "bank": "51000.00"}
    assert rp["total_receipts"] == rp["total_payments"] == "160000.00" and rp["balanced"]
    sheet = r["statements"]["balance_sheet"]
    assert sheet["capital_fund"] == {"opening": "82000.00", "surplus": "10200.00", "corpus": "10000.00", "closing": "102200.00"}
    assert sheet["assets"] == {"Cash": "16000.00", "Bank": "51000.00", "Accrued Income": "6000.00", "Fixed Assets": "34200.00"}
    assert sheet["liabilities"] == {"Outstanding Expenses": "3000.00", "Income Received in Advance": "2000.00"}
    assert sheet["total_assets"] == "107200.00"
    assert not any(l in r["ledgers"] for l in ("Trading A/c", "Corpus Fund", "Salary and Wages"))


def test_individual_freelancer():
    r = sample("individual_freelancer")
    check(r)
    assert not r["questions"] and r["counts"]["needs_review"] == 0
    ie = r["statements"]["income_expense"]
    assert (ie["total_income"], ie["total_expenses"], ie["savings"]) == ("496000.00", "368000.00", "128000.00")
    assert signed_ledger(r, "Cash") == D("23000")
    assert signed_ledger(r, "Bank") == D("98000")
    assert signed_ledger(r, "Investments") == D("210000")
    assert signed_ledger(r, "Loans") == D("-90000")
    nw = r["statements"]["net_worth"]
    assert nw["opening"]["net_worth"] == "113000.00"
    assert nw["closing_at_cost"]["net_worth"] == "241000.00"
    assert nw["closing_at_market"]["net_worth"] == "256000.00"
    assert nw["closing_at_market"]["unrealised_gain"] == "15000.00"
    assert sum(j.get("category") == "contra" for j in r["journal"]) == 1


@pytest.mark.parametrize("entity", ["business", "nonprofit", "individual"])
def test_random_books(entity):
    rng = random.Random(83471)
    for _ in range(200):
        def money():
            return str(D(rng.randint(0, 100000)) / 100)
        opening = {k: money() for k in ("cash", "debtors", "creditors", "stock", "fixed_assets", "investments", "loans")}
        opening["bank"] = "100000"
        expense = {"business": "Rent Paid", "nonprofit": "Salaries", "individual": "Rent"}[entity]
        income = {"business": "Interest Received", "nonprofit": "Subscriptions", "individual": "Professional Income"}[entity]
        closing = {}
        for target in (opening, closing):
            for key, head in (("outstanding_expenses", expense), ("prepaid_expenses", expense), ("accrued_income", income), ("advance_income", income)):
                target[key] = {head: money()}
        closing.update(depreciation=money())
        if entity == "business":
            closing.update(debtors=str(D(opening["debtors"]) + D(money())), creditors=str(D(opening["creditors"]) + D(money())), stock=money(),
                           discount_allowed=money(), discount_received=money(), bad_debts=money(), sales_returns=money(), purchase_returns=money())
        lines = []
        for _ in range(rng.randint(1, 20)):
            incoming = bool(rng.randrange(2))
            if incoming:
                hints = {"business": ["cash_sale", "debtor_receipt", "capital_introduced", "interest_income", "loan_received", "asset_sale"],
                         "nonprofit": ["subscription", "corpus_donation", "loan_received", "donation"],
                         "individual": ["professional_income", "loan_received", "interest_income", "gift", "asset_sale"]}[entity]
            else:
                hints = ["asset_purchase", "loan_repayment", "expense:" + expense]
                hints += {"business": ["creditor_payment", "cash_purchase", "drawings"], "nonprofit": [], "individual": ["investment", "loan_principal"]}[entity]
            value = money()
            if D(value) == 0:
                value = "0.01"
            lines.append(entry("Synthetic line", receipt=value if incoming else "0", payment="0" if incoming else value,
                               mode=rng.choice(["cash", "bank"]), hint=rng.choice(hints)))
        transfer = money() or "1"
        if D(transfer):
            lines += [entry("Cash deposited into bank", payment=transfer), entry("Cash deposited into bank", receipt=transfer, mode="bank")]
        b = book(entity, lines, opening=opening, closing=closing)
        original = copy.deepcopy(b)
        r = convert(b)
        check(r)
        assert b == original
        assert convert(b) == r
        for mode in ("cash", "bank"):
            expected = D(opening[mode]) + sum((D(l["receipt"]) - D(l["payment"]) for l in lines if l["mode"] == mode), D(0))
            assert signed_ledger(r, mode.title()) == expected
        if entity == "nonprofit":
            assert r["statements"]["receipts_payments"]["balanced"]


@pytest.mark.parametrize("entity", ["business", "nonprofit", "individual"])
def test_empty(entity):
    r = convert(book(entity))
    check(r)
    assert r["counts"] == {"entries": 0, "classified": 0, "needs_review": 0, "excluded": 0}


@pytest.mark.parametrize("bad", [entry(receipt="2", payment="3"), entry(payment="-1"), entry(receipt="garbage"),
                                 entry(), entry(receipt="NaN"), entry(receipt="Infinity"), entry(receipt="1e1000000"),
                                 entry(payment="10", mode="crypto"), entry(receipt="1", date="2026-02-30"), "junk"])
def test_bad_entry(bad):
    r = convert(book(entries=[bad]))
    assert r["errors"] and "Entry 1" in r["errors"][0]
    assert r["counts"]["excluded"] == 1
    assert not r["journal"]


@pytest.mark.parametrize("value", [None, [], "nonsense", {"entity_type": []}, book("unknown"), book(period_start="bad"),
                                   book(period_end="2020-01-01")])
def test_bad_book(value):
    assert convert(value)["errors"]


def test_bad_balances_and_shapes():
    r = convert(book(opening={"cash": "NaN", "outstanding_expenses": [], "prepaid_expenses": {"Cash": "1"}},
                     closing={"stock": "garbage"}, entries="bad"))
    assert len(r["errors"]) == 5
    assert not convert(book(opening=None, closing=None))["errors"]


def test_outside_period():
    r = convert(book(entries=[entry(receipt="10", date="2026-03-31"), entry(payment="2", date="2027-04-01")]))
    assert not r["errors"] and len(r["warnings"]) == 2
    assert r["counts"]["excluded"] == 2 and not r["journal"]


def test_missing_stock_and_debtors():
    r = convert(book(entries=[entry("Debtors receipt", receipt="20")], opening={"debtors": "100", "creditors": "10"}, closing={}))
    assert any("unsold stock" in q for q in r["questions"])
    assert any("customers still owe" in q for q in r["questions"])
    assert any("owe suppliers" in q for q in r["questions"])
    assert any("gross profit is unreliable" in w for w in r["warnings"])
    assert signed_ledger(r, "Debtors") == D("100")
    assert signed_ledger(r, "Creditors") == D("-10")
    check(r)


def test_negative_derived():
    r = convert(book(opening={"debtors": "100", "creditors": "100"}, closing={"debtors": "20", "creditors": "30", "stock": "0"}))
    assert len([q for q in r["questions"] if q.startswith("ERROR:")]) == 2
    assert not any(j["source"] == "derived" for j in r["journal"])
    assert not r["crosscheck"]["agrees"]


def test_contra_pair_and_unmatched():
    lines = [entry("ATM cash withdrawal", receipt="30"), entry("ATM cash withdrawal", payment="30", mode="bank"),
             entry("ATM cash withdrawal", payment="30", mode="bank")]
    r = convert(book(entries=lines, opening={"bank": "100"}))
    check(r)
    assert len([j for j in r["journal"] if j.get("category") == "contra"]) == 2
    assert len(r["warnings"]) == 1 and "unmatched contra" in r["warnings"][0]
    assert signed_ledger(r, "Cash") == 60 and signed_ledger(r, "Bank") == 40


def test_hints_unknowns_and_emi():
    r = convert(book(entries=[entry("Purchase of goods", payment="20", hint="asset_purchase"),
                             entry("Synthetic fee", payment="5", hint="expense:Professional Fees"),
                             entry("Unknown notebook payment", payment="2"), entry(receipt="10")]))
    check(r)
    assert signed_ledger(r, "Fixed Assets") == 20
    assert r["statements"]["profit_loss"]["expenses"]["Professional Fees"] == "5.00"
    assert r["counts"]["needs_review"] == 1
    unlabelled = next(j for j in r["journal"] if j.get("category") == "cash_sale")
    assert unlabelled["confidence"] == 0.7
    r = convert(book("individual", [entry("Home loan EMI", payment="500")]))
    check(r)
    assert r["counts"]["needs_review"] == 1
    assert "principal/interest split" in r["questions"][0]
    assert r["statements"]["income_expense"]["expenses"] == {"Interest Paid": "500.00"}


def test_capital_depreciation_returns_and_opening_reversals():
    opening = {"cash": "1000", "fixed_assets": "1000", "stock": "20", "capital": "999",
               "outstanding_expenses": {"Rent Paid": "10"}, "prepaid_expenses": {"Insurance": "20"},
               "accrued_income": {"Rent Received": "30"}, "advance_income": {"Commission Received": "40"}}
    closing = {"stock": "30", "debtors": "50", "creditors": "60", "sales_returns": "5", "purchase_returns": "6",
               "prepaid_expenses": {"Insurance": "5"}, "outstanding_expenses": {"Rent Paid": "15"},
               "accrued_income": {"Rent Received": "10"}, "advance_income": {"Commission Received": "20"}, "depreciation_rate": "10"}
    r = convert(book(entries=[entry("Purchase of computer", payment="100"), entry("Sale of old computer", receipt="50")], opening=opening, closing=closing))
    check(r)
    assert any("999.00" in w and "2020.00" in w for w in r["warnings"])
    assert "additions depreciated for a full year" in r["warnings"]
    assert any("profit/loss on sale" in w for w in r["warnings"])
    assert r["statements"]["profit_loss"]["expenses"] == {"Rent Paid": "5.00", "Insurance": "15.00", "Depreciation": "110.00"}
    assert r["statements"]["profit_loss"]["other_income"] == {"Rent Received": "-20.00", "Commission Received": "20.00"}
    assert signed_ledger(r, "Fixed Assets") == 940
    closing["depreciation"] = "25"
    r = convert(book(opening=opening, closing=closing))
    assert r["statements"]["profit_loss"]["expenses"]["Depreciation"] == "25.00"
    assert "additions depreciated for a full year" not in r["warnings"]


def test_csv():
    text = '\ufeffExample synthetic cash book\nFor this year\nDate,Particulars,Received,Paid,Type,Name,Hint\n01/04/2026,"Sales, counter","1,234.50",,cash,Example,cash_sale\n02-04-26,Rent,,"1,000",bank,,expense:Rent Paid\n03-Apr-2026,Interest,10,,bank,,\n2026-04-04,Sale,20,,cash,,\n,Totals,"1,264.50","1,000",,,\n'
    parsed = parse_cash_book_csv(text)
    assert not parsed["errors"] and parsed["skipped"] == 3
    assert [e["date"] for e in parsed["entries"]] == ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]
    assert parsed["entries"][0]["receipt"] == "1,234.50"
    check(convert(book(entries=parsed["entries"])))
    signed = parse_cash_book_csv('Date,Details,Amount\n2026-04-01,Sale,"+1,234.50"\n2026-04-02,Rent,-100\n')
    assert signed["entries"][0]["receipt"] == "1234.50" and signed["entries"][1]["payment"] == "100.00"
    assert not signed["errors"]


@pytest.mark.parametrize("text", [None, "no header", "Date,Details,Amount\nbad,Sale,1\n", "Date,Details,Amount\n2026-04-01,Sale,+-1\n",
                                  "Date,Details,In,Out\n2026-04-01,Sale,1,2\n", "Date,Details,Amount\n2026-04-01,Sale,NaN\n"])
def test_csv_errors(text):
    assert parse_cash_book_csv(text)["errors"]


@pytest.mark.parametrize("name", ["business_textbook", "nonprofit_club", "individual_freelancer"])
def test_tally(name):
    r = sample(name)
    out = to_tally(r)
    assert len(out["vouchers"]) == len([j for j in r["journal"] if j["source"] != "closing"])
    assert all(v.balanced() for v in out["vouchers"])
    assert len({l.name for l in out["ledgers"]}) == len(out["ledgers"])
    groups = {l.name: l.parent for l in out["ledgers"]}
    assert groups["Cash"] == "Cash-in-Hand" and groups["Bank"] == "Bank Accounts"
    for v in out["vouchers"]:
        if v.vtype in {"Receipt", "Payment"}:
            assert v.lines[-1].ledger in {"Cash", "Bank"}
            assert v.lines[0].ledger not in {"Cash", "Bank"}
        if v.vtype == "Contra":
            assert {l.ledger for l in v.lines} == {"Cash", "Bank"}
    assert "Trading A/c" not in groups and "Income & Expenditure A/c" not in groups


def test_tally_bad_data():
    assert to_tally(None) == {"ledgers": [], "vouchers": []}
    assert to_tally({"journal": [None, {"source": "opening", "lines": []}]}) == {"ledgers": [], "vouchers": []}
