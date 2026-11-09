"""Independent acceptance tests for the single-entry -> double-entry conversion.
Expected figures are hand-computed (see docs/samples/single_entry) or come from scripts/single_entry_sim.py, which knows the TRUE
profit and balances of a simulated shop that the cash book alone does not reveal."""
import importlib.util
import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from taxsetu_engine.single_entry import convert

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    return json.loads((ROOT / "docs" / "samples" / "single_entry" / name).read_text(encoding="utf-8"))


def simulate(seed):
    spec = importlib.util.spec_from_file_location("single_entry_sim", ROOT / "scripts" / "single_entry_sim.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.simulate(seed)


def m(x):
    return D(x)


def bal(r, name):
    """Post-closing ledger balance, debit positive."""
    row = r["ledgers"].get(name)
    return D(0) if not row else (D(row["balance"]) if row["side"] == "Dr" else -D(row["balance"]))


def tb(r):
    return {row["ledger"]: D(row["debit"]) - D(row["credit"]) for row in r["trial_balance"]["rows"]}


def healthy(r):
    assert not r["errors"], r["errors"]
    assert r["trial_balance"]["balanced"] and r["statements"]["balance_sheet"]["balanced"] and r["crosscheck"]["agrees"], r["crosscheck"]
    for j in r["journal"]:
        dr = sum(D(l["amount"]) for l in j["lines"] if l["side"] == "Dr")
        cr = sum(D(l["amount"]) for l in j["lines"] if l["side"] == "Cr")
        assert dr == cr and dr > 0, j


def test_business_textbook_case():
    r = convert(load("business_textbook.json"))
    healthy(r)
    s, t, p, b = r["statements"], r["statements"]["trading"], r["statements"]["profit_loss"], r["statements"]["balance_sheet"]
    assert [m(t[k]) for k in ("net_sales", "net_purchases", "cost_of_goods_sold", "gross_profit")] == [m("770000"), m("381500"), m("366500"), m("403500")]
    assert m(p["total_expenses"]) == m("196000") and m(p["total_other_income"]) == m("3500") and m(p["net_profit"]) == m("211000")
    assert m(p["expenses"]["Rent Paid"]) == m("65000")                                                        # 60,000 paid + 5,000 outstanding
    assert [m(b["capital"][k]) for k in ("opening", "introduced", "net_profit", "drawings", "closing")] == [m("120000"), m("50000"), m("211000"), m("72000"), m("309000")]
    assert m(b["total_assets"]) == m("354000") == m(b["total_liabilities_and_capital"])
    assert (bal(r, "Cash"), bal(r, "Bank"), bal(r, "Debtors"), bal(r, "Stock-in-Trade"), bal(r, "Fixed Assets")) == (m("13000"), m("166000"), m("55000"), m("75000"), m("45000"))
    assert (-bal(r, "Creditors"), -bal(r, "Outstanding Expenses")) == (m("40000"), m("5000"))
    derived = {j["narration"]: j for j in r["journal"] if j["source"] == "derived"}
    amounts = sorted(D(l["amount"]) for j in derived.values() for l in j["lines"] if l["side"] == "Dr")
    assert m("370000") in amounts and m("281500") in amounts                                                 # credit sales / credit purchases found by the conversion method
    assert sum(1 for j in r["journal"] if j["source"] == "cash_book" and "deposited" in j["narration"].lower()) == 1      # the contra listed in both books is posted once
    assert r["counts"]["needs_review"] == 0 and not r["questions"]
    assert tb(r)["Debtors"] == m("55000") and tb(r)["Stock-in-Trade"] == m("60000")                        # adjusted trial balance still carries OPENING stock


def test_nonprofit_club_case():
    r = convert(load("nonprofit_club.json"))
    healthy(r)
    ie, rp, bs = r["statements"]["income_expenditure"], r["statements"]["receipts_payments"], r["statements"]["balance_sheet"]
    assert m(ie["income"]["Subscriptions"]) == m("60000") and m(ie["expenditure"]["Salaries"]) == m("37000")
    assert [m(ie[k]) for k in ("total_income", "total_expenditure", "surplus")] == [m("100000"), m("89800"), m("10200")]
    assert m(ie["expenditure"]["Depreciation"]) == m("3800")
    assert [m(bs["capital_fund"][k]) for k in ("opening", "surplus", "corpus", "closing")] == [m("82000"), m("10200"), m("10000"), m("102200")]
    assert m(bs["total_assets"]) == m("107200") and m(bs["total_liabilities_and_capital"]) == m("107200")
    assert m(bs["liabilities"]["Outstanding Expenses"]) == m("3000") and m(bs["liabilities"]["Income Received in Advance"]) == m("2000")
    assert (m(rp["opening"]["cash"]) + m(rp["opening"]["bank"]), m(rp["closing"]["cash"]), m(rp["closing"]["bank"])) == (m("50000"), m("16000"), m("51000"))
    assert m(rp["total_receipts"]) == m("160000") == m(rp["total_payments"]) and rp["balanced"]
    assert "Capital Fund" in r["ledgers"] and bal(r, "Cash") == m("16000") and bal(r, "Bank") == m("51000")


def test_individual_case():
    r = convert(load("individual_freelancer.json"))
    healthy(r)
    ie, nw = r["statements"]["income_expense"], r["statements"]["net_worth"]
    assert [m(ie[k]) for k in ("total_income", "total_expenses", "savings")] == [m("496000"), m("368000"), m("128000")]
    assert (bal(r, "Cash"), bal(r, "Bank"), bal(r, "Investments"), -bal(r, "Loans")) == (m("23000"), m("98000"), m("210000"), m("90000"))
    assert m(nw["opening"]["net_worth"]) == m("113000") and m(nw["closing_at_cost"]["net_worth"]) == m("241000")
    assert m(nw["closing_at_market"]["net_worth"]) == m("256000") and m(nw["closing_at_market"]["unrealised_gain"]) == m("15000")
    assert r["counts"]["needs_review"] == 0
    assert sum(1 for j in r["journal"] if j["source"] == "cash_book" and "atm" in j["narration"].lower()) == 1


@pytest.mark.parametrize("seed", range(1, 31))
def test_converted_books_reproduce_the_true_figures_of_a_simulated_shop(seed):
    book, truth = simulate(seed)
    r = convert(book)
    healthy(r)
    t, p, b = r["statements"]["trading"], r["statements"]["profit_loss"], r["statements"]["balance_sheet"]
    assert m(t["net_sales"]) == truth["sales"], "total sales (cash + the credit sales that never touched the cash book)"
    assert m(t["net_purchases"]) == truth["purchases"]
    assert m(t["gross_profit"]) == truth["gross_profit"] and m(p["net_profit"]) == truth["net_profit"]
    assert (bal(r, "Cash"), bal(r, "Bank")) == (truth["cash"], truth["bank"])
    assert (bal(r, "Debtors"), -bal(r, "Creditors"), -bal(r, "Loans")) == (truth["debtors"], truth["creditors"], truth["loans"])
    assert m(b["total_assets"]) == truth["total_assets"] and m(b["capital"]["closing"]) == truth["capital"] and m(b["capital"]["opening"]) == truth["opening_capital"]
    assert r["counts"]["needs_review"] == 0, [j for j in r["journal"] if j.get("flags")][:3]
    assert r["counts"]["excluded"] == 0 and not r["warnings"], r["warnings"]


def test_the_converter_is_deterministic_and_does_not_touch_its_input():
    book, _ = simulate(3)
    snapshot = json.dumps(book, sort_keys=True)
    a, b = convert(book), convert(book)
    assert json.dumps(book, sort_keys=True) == snapshot and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_blank_spreadsheet_cells_mean_zero():
    base = {"entity_type": "individual", "name": "t", "period_start": "2026-04-01", "period_end": "2027-03-31", "opening": {"cash": "100"}}
    for blank in ("", None, " ", "0", "0.00"):
        r = convert({**base, "entries": [{"date": "2026-05-01", "description": "Freelance client payment", "receipt": "500", "payment": blank},
                                         {"date": "2026-05-02", "description": "House rent", "receipt": blank, "payment": "200"}]})
        assert not r["errors"], (blank, r["errors"])
        assert bal(r, "Cash") == m("400")                                         # 100 + 500 - 200
