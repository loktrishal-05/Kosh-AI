"""GST in the books and profit/loss on selling an asset. Every expected figure below was worked out on paper first."""
from decimal import Decimal as D

from taxsetu_engine.single_entry import convert, to_tally


def book(entries, opening=None, closing=None):
    return {"entity_type": "business", "name": "T", "period_start": "2026-04-01", "period_end": "2027-03-31",
            "opening": opening or {}, "closing": {"debtors": "0", "creditors": "0", "stock": "0", **(closing or {})}, "entries": entries}


def line(day, text, receipt="", payment="", **extra):
    return {"date": day, "description": text, "receipt": receipt, "payment": payment, "mode": "cash", **extra}


def sound(r):
    assert r["errors"] == []
    assert r["trial_balance"]["balanced"] and r["statements"]["balance_sheet"]["balanced"] and r["crosscheck"]["agrees"], r["crosscheck"]
    return r


def ledger(r, name):
    row = r["ledgers"].get(name)
    return D(0) if not row else (D(row["balance"]) if row["side"] == "Dr" else -D(row["balance"]))


OPEN = {"cash": "100000", "fixed_assets": "50000"}


def test_asset_sold_below_book_value_is_a_loss():
    r = sound(convert(book([line("2026-06-10", "Sale of old computer", "20000", book_value="30000")], OPEN)))
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("-10000")
    assert D(r["statements"]["profit_loss"]["expenses"]["Loss on Sale of Asset"]) == D("10000")
    assert ledger(r, "Fixed Assets") == D("20000") and ledger(r, "Cash") == D("120000")
    assert D(r["statements"]["balance_sheet"]["capital"]["closing"]) == D("140000")
    assert not any("book value" in q for q in r["questions"])


def test_asset_sold_above_book_value_is_a_profit_and_zero_book_value_is_all_profit():
    r = sound(convert(book([line("2026-06-10", "Sale of old computer", "45000", book_value="30000")], OPEN)))
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("15000") and ledger(r, "Fixed Assets") == D("20000")
    assert D(r["statements"]["profit_loss"]["other_income"]["Profit on Sale of Asset"]) == D("15000")
    r = sound(convert(book([line("2026-06-10", "Sale of old computer", "5000", book_value="0")], OPEN)))
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("5000") and ledger(r, "Fixed Assets") == D("50000")


def test_asset_sale_without_book_value_is_asked_about_not_guessed():
    r = sound(convert(book([line("2026-06-10", "Sale of old computer", "20000")], OPEN)))
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("0") and any("book value" in q for q in r["questions"])


def test_bad_book_value_or_gst_rate_excludes_the_line_with_an_error():
    for extra in ({"book_value": "abc"}, {"book_value": "-5"}, {"gst_rate": "7"}):
        r = convert(book([line("2026-06-10", "Cash sales", "1000", **extra)]))
        assert r["counts"]["excluded"] == 1 and any("invalid gst_rate" in e for e in r["errors"]), extra


GST_YEAR = [line("2026-04-10", "Cash sales", "11800", gst_rate="18"),
            line("2026-04-12", "Cash purchases of goods", payment="5600", gst_rate="12"),
            line("2026-04-15", "Shop rent paid", payment="5900", gst_rate="18")]


def test_gst_is_split_out_and_the_credit_is_set_off_against_tax_paid():
    r = sound(convert(book([*GST_YEAR, line("2026-05-20", "GST paid to government", payment="300")], {"cash": "100000"}, {"stock": "2000"})))
    s = r["statements"]
    assert D(s["trading"]["sales"]) == D("10000") and D(s["trading"]["purchases"]) == D("5000") and D(s["trading"]["gross_profit"]) == D("7000")
    assert D(s["profit_loss"]["net_profit"]) == D("2000")
    assert s["gst"] == {"output_tax_collected": "1800.00", "input_tax_credit": "1500.00", "paid_to_government": "300.00", "refunds_received": "0.00",
                        "set_off": "1500.00", "payable_at_end": "0.00", "credit_carried_forward": "0.00"}
    assert ledger(r, "Cash") == D("100000") and D(s["balance_sheet"]["capital"]["closing"]) == D("102000")


def test_gst_left_unpaid_shows_as_a_liability():
    r = sound(convert(book(GST_YEAR, {"cash": "100000"}, {"stock": "2000"})))
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("2000")                       # tax never touches profit
    assert r["statements"]["gst"]["payable_at_end"] == "300.00"
    assert r["statements"]["balance_sheet"]["liabilities"]["Output GST"] == "300.00"
    assert ledger(r, "Cash") == D("100300")


def test_credit_sales_gst_rate_separates_tax_from_derived_sales():
    r = sound(convert(book([], {"cash": "100000"}, {"debtors": "11800", "credit_sales_gst_rate": "18"})))
    assert D(r["statements"]["trading"]["sales"]) == D("10000") and r["statements"]["gst"]["payable_at_end"] == "1800.00"
    assert D(r["statements"]["profit_loss"]["net_profit"]) == D("10000") and ledger(r, "Debtors") == D("11800")


def test_credit_purchases_gst_rate_creates_input_credit_and_missing_rate_is_asked():
    r = sound(convert(book([], {"cash": "100000"}, {"creditors": "11200", "stock": "10000", "credit_purchases_gst_rate": "12"})))
    assert D(r["statements"]["trading"]["purchases"]) == D("10000") and r["statements"]["gst"]["credit_carried_forward"] == "1200.00"
    r = sound(convert(book([line("2026-04-10", "Cash sales", "11800", gst_rate="18")], {"cash": "100000"}, {"debtors": "5900"})))
    assert any("credit sales carry GST" in q for q in r["questions"])


def test_gst_ignored_where_it_does_not_apply_and_paying_more_than_collected_is_questioned():
    r = convert(book([line("2026-04-10", "Capital introduced by owner", "1000", gst_rate="18")]))
    assert any("GST rate ignored" in w for w in r["warnings"]) and "gst" not in r["statements"]
    r = sound(convert(book([line("2026-05-20", "GST paid to government", payment="300")], {"cash": "100000"})))
    assert any("more than GST collected" in q for q in r["questions"])


def test_gst_refund_is_not_mistaken_for_other_income():
    r = sound(convert(book([line("2026-04-12", "Cash purchases of goods", payment="5600", gst_rate="12"), line("2026-06-01", "GST refund received", receipt="600")],
                           {"cash": "100000"}, {"stock": "5000"})))
    assert r["questions"] == [] and r["statements"]["gst"]["refunds_received"] == "600.00" and ledger(r, "Input GST") == D("0")


def test_individuals_and_clubs_ignore_gst():
    b = book([line("2026-04-10", "Freelance client payment", "1180", gst_rate="18")])
    b["entity_type"] = "individual"
    r = convert(b)
    assert "gst" not in r["statements"] and any("businesses only" in w for w in r["warnings"])


def test_tally_export_files_gst_and_asset_ledgers_in_the_right_groups_and_stays_balanced():
    r = sound(convert(book([*GST_YEAR, line("2026-06-10", "Sale of old computer", "20000", book_value="30000")], {**OPEN, "cash": "100000"}, {"stock": "2000"})))
    out = to_tally(r)
    groups = {l.name: l.parent for l in out["ledgers"]}
    assert groups["Input GST"] == groups["Output GST"] == "Duties & Taxes" and groups["Fixed Assets"] == "Fixed Assets"
    assert groups["Loss on Sale of Asset"] == "Indirect Expenses"
    assert out["vouchers"] and all(v.balanced() for v in out["vouchers"])


# ---- simulated GST-registered shops: the simulator knows the true figures, the converter sees only the cash book ----------------------------
import importlib.util
from pathlib import Path

import pytest


def simulate(seed, **kw):
    spec = importlib.util.spec_from_file_location("single_entry_sim", Path(__file__).resolve().parents[2] / "scripts" / "single_entry_sim.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.simulate(seed, **kw)


@pytest.mark.parametrize("seed", range(1, 21))
@pytest.mark.parametrize("options", [{"gst": True}, {"sale": True}, {"gst": True, "sale": True}])
def test_simulated_shop_with_gst_and_an_asset_sale_matches_the_truth(seed, options):
    b, truth = simulate(seed, **options)
    r = sound(convert(b))
    s = r["statements"]
    assert D(s["trading"]["sales"]) == truth["sales"] and D(s["trading"]["purchases"]) == truth["purchases"]
    assert D(s["trading"]["gross_profit"]) == truth["gross_profit"] and D(s["profit_loss"]["net_profit"]) == truth["net_profit"]
    assert (ledger(r, "Cash"), ledger(r, "Bank"), ledger(r, "Debtors")) == (truth["cash"], truth["bank"], truth["debtors"])
    assert ledger(r, "Fixed Assets") == truth["fixed_assets"] and D(s["balance_sheet"]["total_assets"]) == truth["total_assets"]
    assert D(s["balance_sheet"]["capital"]["closing"]) == truth["capital"]
    if options.get("gst"):
        g = s["gst"]
        assert (D(g["output_tax_collected"]), D(g["input_tax_credit"]), D(g["paid_to_government"])) == (truth["output_tax"], truth["input_tax"], truth["gst_paid"])
        assert (D(g["payable_at_end"]), D(g["credit_carried_forward"])) == (truth["gst_payable"], truth["itc_carried_forward"])
    else:
        assert "gst" not in s
    if options.get("sale"):
        assert D(s["profit_loss"]["expenses"]["Loss on Sale of Asset"]) == D("5000")
    assert not any("book value" in q for q in r["questions"])
