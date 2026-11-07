from datetime import date
from decimal import Decimal as D
import xml.etree.ElementTree as ET

import pytest
from taxsetu_engine import payments as p
from taxsetu_engine.tally import purchase_voucher_xml

GOOD = [(True, True)] * 6


@pytest.mark.parametrize("months,active,blocked,score", [
    (GOOD, True, False, 900), ([(True, False)] * 6, True, False, 450), ([(False, False)] * 6, True, False, 0),
    (GOOD, False, False, 0), (GOOD, True, True, 800), ([], True, False, 0), ([(True, True)] * 5 + [(False, False)], True, False, 750),
])
def test_trust_score(months, active, blocked, score):
    assert p.supplier_trust_score(months, active, blocked) == score


def test_report_example_118000_split():
    s = p.split_payment(100000, 18000, trust_score=500, tds_section="194C")
    assert (s.base_payout, s.tds, s.gst_escrow, s.total) == (D("98000.00"), D("2000.00"), D("18000"), D("118000.00"))


def test_trusted_supplier_gets_gst_upfront():
    s = p.split_payment(100000, 18000, trust_score=850, tds_section="194C")
    assert s.gst_escrow == 0 and s.gst_paid_direct == D("18000.00") and s.base_payout == D("116000.00")


@pytest.mark.parametrize("taxable,gst,score,sec", [(100000, 18000, 100, None), (33333.33, 5999.99, 799, "194J"),
                                                   (1, 0, 0, None), (250000, 45000, 900, "194C"), (99999.99, 17999.99, 0, "194H")])
def test_split_conserves_total_and_ledger_balances(taxable, gst, score, sec):
    s = p.split_payment(taxable, gst, score, sec)
    assert s.base_payout + s.tds + s.gst_escrow == s.total
    rows = p.purchase_ledger_entries(taxable, gst, s)
    assert sum(r[1] for r in rows) == sum(r[2] for r in rows)


def test_blocked_credit_goes_to_purchase_cost_not_itc():
    s = p.split_payment(10000, 1800, 900)
    rows = p.purchase_ledger_entries(10000, 1800, s, blocked_17_5=True)
    assert rows[0][1] == D("11800.00") and not any("Credit Ledger" in r[0] for r in rows)


def test_escrowed_itc_is_booked_as_deferred():
    s = p.split_payment(10000, 1800, 100)
    assert any("deferred" in r[0] for r in p.purchase_ledger_entries(10000, 1800, s))


def test_settlement_unbundling_and_report_arithmetic_flag():
    u = p.unbundle_settlement(100000, 1500, 270, 500, 100)
    assert u["bank"] == D("97630.00")   # NB: the report's example quotes 97,820; its own deductions sum to 2,370, so 97,630
    assert u["gross_sales"] - u["bank"] == D("2370.00")


def test_tally_xml_is_well_formed_and_balanced():
    s = p.split_payment(100000, 18000, 100, "194C")
    xml = purchase_voucher_xml("Demo Co & Sons", "Ramesh <Traders>", "INV/402", date(2026, 11, 7),
                               p.purchase_ledger_entries(100000, 18000, s))
    root = ET.fromstring(xml)                         # special characters must be escaped, not break the document
    amounts = [D(a.text) for a in root.iter("AMOUNT")]
    assert sum(amounts) == 0                          # Tally: debits negative, credits positive -> nets to zero
    assert root.find(".//VOUCHERNUMBER").text == "INV/402" and root.find(".//DATE").text == "20261107"
    assert root.find(".//PARTYLEDGERNAME").text == "Ramesh <Traders>"
