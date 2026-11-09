"""Opt-in test against a REAL running TallyPrime (HTTP server on, a test company open). Skipped unless TALLY_LIVE_COMPANY is set:
    TALLY_LIVE_COMPANY="TaxSetu Test Books" TALLY_URL=http://127.0.0.1:9000 pytest tests/live -q
Education mode only accepts the 1st, 2nd and last day of a month, so vouchers use the 2nd of the current month.
Masters are idempotent; each run adds one more of each voucher to the TEST company, so never point this at real books."""
import os
import re
import urllib.request
from datetime import date
from decimal import Decimal as D

import pytest
from taxsetu_engine import gst, tally_coa, tallybooks as tb
from taxsetu_engine.tally_models import BookContext, LedgerSpec, Line, VoucherDraft

CO = os.environ.get("TALLY_LIVE_COMPANY", "")
URL = os.environ.get("TALLY_URL", "http://127.0.0.1:9000")
pytestmark = pytest.mark.skipif(not CO, reason="set TALLY_LIVE_COMPANY to run against a real TallyPrime")
DAY = date.today().replace(day=2)
CTX = BookContext(company=CO, state_code="29")


def post(xml):
    req = urllib.request.Request(URL, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8"})
    return urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")


def gstin(pan):
    base = "29" + pan + "1Z"
    return base + gst.gstin_check_char(base)


def test_starter_chart_imports_cleanly():
    r = tb.parse_response(post(tb.masters_xml(CO, tally_coa.starter_pack("trader", "29"))))
    assert r["ok"] and not r["errors"], r


def test_every_voucher_type_is_accepted_and_recorded_with_the_right_amounts():
    sup, cus = gstin("ABCDE1234F"), gstin("PQRST5678K")
    assert tb.parse_response(post(tb.masters_xml(CO, [LedgerSpec("Gupta Traders", "Sundry Creditors", gstin=sup, state="29"),
                                                        LedgerSpec("Rao Traders", "Sundry Debtors", gstin=cus, state="29")])))["ok"]
    drafts = [
        VoucherDraft("Payment", DAY, (Line("Rent Paid", D("25000"), "Dr"), Line("Bank Account", D("25000"), "Cr"))),
        VoucherDraft("Receipt", DAY, (Line("Bank Account", D("1200"), "Dr"), Line("Interest Received", D("1200"), "Cr"))),
        VoucherDraft("Contra", DAY, (Line("Cash", D("5000"), "Dr"), Line("Bank Account", D("5000"), "Cr"))),
        tb.purchase_draft(CTX, date=DAY, supplier="Gupta Traders", supplier_gstin=sup, invoice_no="GT/1", taxable="50000", rate_pct="18"),
        tb.sales_draft(CTX, date=DAY, customer="Rao Traders", customer_gstin=cus, invoice_no="S-1", taxable="30000", rate_pct="18"),
    ]
    for d in drafts:
        r = tb.parse_response(post(tb.voucher_xml(CO, [d])))
        assert r["ok"] and r["created"] == 1, (d.vtype, r)
    rows = tb.parse_daybook_export(post(tb.export_daybook_request(CO, DAY, DAY)))
    got = {(r["vtype"], r["party"], r["amount"]) for r in rows if r["date"] == DAY.isoformat()}
    assert ("Purchase", "Gupta Traders", "50000.00") in got and ("Sales", "Rao Traders", "30000.00") in got
    assert any(t == "Payment" and a == "25000.00" for t, _, a in got)


def test_a_missing_ledger_is_reported_not_silently_accepted():
    d = VoucherDraft("Payment", DAY, (Line("No Such Ledger XYZ", D("1"), "Dr"), Line("Bank Account", D("1"), "Cr")))
    r = tb.parse_response(post(tb.voucher_xml(CO, [d])))
    assert not r["ok"]


def test_unknown_company_is_a_clear_error():
    r = post(tb.export_ledgers_request("No Such Company 12345"))
    assert "Could not set" in r and tb.parse_ledger_export(r) == []


def test_resending_a_batch_does_not_duplicate_vouchers():
    """REMOTEID: the second send alters in place. Counts are read back from Tally itself."""
    day = date.today().replace(day=1)
    marker = D("7777.77")
    drafts = [VoucherDraft("Payment", day, (Line("Rent Paid", marker, "Dr"), Line("Bank Account", marker, "Cr")), narration="idempotency probe")] * 2   # two identical entries
    xml = tb.voucher_xml(CO, drafts, remote_id_prefix="ts-live-" + os.urandom(4).hex())
    first, second = tb.parse_response(post(xml)), tb.parse_response(post(xml))
    assert first["ok"] and first["created"] == 2
    assert second["created"] == 0 and second["altered"] == 2, second                 # retried in place, nothing new
    rows = tb.parse_daybook_export(post(tb.export_daybook_request(CO, day, day)))
    mine = [r for r in rows if r["vtype"] == "Payment" and r["amount"] == "7777.77" and r["date"] == day.isoformat()]
    assert len(mine) % 2 == 0 and len(mine) >= 2                                      # identical entries stayed separate, retry added none
