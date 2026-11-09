from dataclasses import replace
from datetime import date
from decimal import Decimal
import xml.etree.ElementTree as ET

import pytest

from taxsetu_engine import gst, tallybooks as books
from taxsetu_engine.tally_models import BookContext, LedgerSpec, Line, VoucherDraft


DAY = date(2026, 4, 2)
CTX = BookContext(company='Example & <Co> "Books"', state_code="29")


def gstin(state):
    prefix = state + "ABCDE1234F1Z"
    return prefix + gst.gstin_check_char(prefix)


def purchase(**changes):
    args = dict(date=DAY, supplier="Example Supplier", supplier_gstin=gstin("29"), invoice_no="INV-1",
                taxable="100.05", rate_pct="18")
    args.update(changes)
    return books.purchase_draft(CTX, **args)


def test_voucher_xml():
    name = 'Example & <Shop> "A"\x00\x01\ud800\ufffe'
    draft = purchase(supplier=name, purchase_ledger=name, number="D-1")
    draft = replace(draft, narration="\x00" + "x" * 260)
    root = ET.fromstring(books.voucher_xml(CTX.company, [draft, purchase()]))
    assert root.findtext("HEADER/VERSION") == "1"
    assert root.findtext("HEADER/TALLYREQUEST") == "Import"
    assert root.findtext("HEADER/TYPE") == "Data"
    assert root.findtext("HEADER/ID") == "Vouchers"
    assert root.findtext("BODY/DESC/STATICVARIABLES/SVCURRENTCOMPANY") == CTX.company
    assert len(root.findall(".//REQUESTDATA")) == 1
    vouchers = root.findall(".//REQUESTDATA/TALLYMESSAGE/VOUCHER")
    assert len(vouchers) == 2
    v = vouchers[0]
    assert v.attrib == {"VCHTYPE": "Purchase", "ACTION": "Create", "OBJVIEW": "Accounting Voucher View"}
    assert v.findtext("PARTYLEDGERNAME") == 'Example & <Shop> "A"'
    assert v.findtext("DATE") == v.findtext("EFFECTIVEDATE") == "20260402"
    assert v.findtext("REFERENCE") == "INV-1"
    assert v.findtext("REFERENCEDATE") == "20260402"
    assert v.findtext("VOUCHERNUMBER") == "D-1"
    assert vouchers[1].find("VOUCHERNUMBER") is None
    assert v.findtext("PLACEOFSUPPLY") == "Karnataka"
    assert v.findtext("GSTREGISTRATIONTYPE") == "Regular"
    assert len(v.findtext("NARRATION")) == 250
    for v in vouchers:
        entries = v.findall("ALLLEDGERENTRIES.LIST")
        assert sum(Decimal(e.findtext("AMOUNT")) for e in entries) == 0
        for entry in entries:
            assert (Decimal(entry.findtext("AMOUNT")) < 0) == (entry.findtext("ISDEEMEDPOSITIVE") == "Yes")


@pytest.mark.parametrize("lines", [(), (Line("Purchases", Decimal("1"), "Dr"),),
    (Line("A", Decimal("1"), "wrong"), Line("B", Decimal("1"), "wrong")),
    (Line("A", Decimal("-1"), "Dr"), Line("B", Decimal("-1"), "Cr")),
    (Line("A", Decimal("1.001"), "Dr"), Line("B", Decimal("1.001"), "Cr")),
    (Line("A", Decimal("NaN"), "Dr"),)])
def test_refuse_invalid_drafts(lines):
    with pytest.raises(ValueError):
        books.voucher_xml("Example", [VoucherDraft("Journal", DAY, lines)])


def test_masters_xml():
    name = 'Example & <Ledger> "B"\x00'
    ledgers = [LedgerSpec(name, "Sundry Creditors", gstin("29"), "29"),
               LedgerSpec(name, "Wrong parent"), LedgerSpec("Input CGST", "Wrong parent", gst_duty_head="Central Tax"),
               LedgerSpec("Example Buyer", "Sundry Debtors", state="27"), LedgerSpec("Cash", "Cash-in-Hand")]
    root = ET.fromstring(books.masters_xml(CTX.company, ledgers))
    assert root.findtext(".//REPORTNAME") == "All Masters"
    result = root.findall(".//LEDGER")
    assert len(result) == 4
    assert result[0].get("NAME") == name[:-1]
    assert result[0].get("ACTION") == "Create"
    assert result[0].findtext("PARENT") == "Sundry Creditors"
    assert result[0].findtext("ISBILLWISEON") == "Yes"
    assert result[0].findtext("LEDSTATENAME") == "Karnataka"
    assert result[0].findtext("PARTYGSTIN") == gstin("29")
    assert result[0].findtext("GSTREGISTRATIONTYPE") == "Regular"
    assert result[1].findtext("PARENT") == "Duties & Taxes"
    assert result[1].findtext("TAXTYPE") == "GST"
    assert result[1].findtext("GSTDUTYHEAD") == "Central Tax"
    assert result[2].findtext("ISBILLWISEON") == "Yes"
    assert result[3].findtext("ISBILLWISEON") == "No"
    assert result[3].findtext("GSTREGISTRATIONTYPE") == "Unregistered/Consumer"


def test_success_response():
    reply = """<RESPONSE><CREATED>2</CREATED><ALTERED>1</ALTERED><DELETED>0</DELETED>
        <LASTVCHID>3</LASTVCHID><LASTMID>0</LASTMID><COMBINED>0</COMBINED><IGNORED>0</IGNORED>
        <ERRORS>0</ERRORS><CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS></RESPONSE>"""
    assert books.parse_response(reply) == dict(ok=True, created=2, altered=1, errors=[], raw_status="")


@pytest.mark.parametrize("reply, error", [
    ("<RESPONSE><CREATED>1</CREATED><LINEERROR>Example ledger missing</LINEERROR></RESPONSE>", "Example ledger missing"),
    ("<RESPONSE><CREATED>1</CREATED><ERRORS>1</ERRORS></RESPONSE>", "errors"),
    ("<RESPONSE><CREATED>1</CREATED><EXCEPTIONS>1</EXCEPTIONS></RESPONSE>", "exceptions"),
    ("<RESPONSE><CREATED>bad</CREATED></RESPONSE>", "invalid"),
    ("<RESPONSE><CREATED>-1</CREATED></RESPONSE>", "Negative"),
    ("<RESPONSE/>", "No vouchers"),
    ("garbage", "syntax"), ("", "Empty"),
    ('<!DOCTYPE x [<!ENTITY a "boom">]><RESPONSE>&a;</RESPONSE>', "forbidden"),
    ('<!ENTITY a "boom"><RESPONSE/>', "forbidden"),
])
def test_failed_response(reply, error):
    result = books.parse_response(reply)
    assert not result["ok"]
    assert error in " ".join(result["errors"])


def test_failure_envelope():
    result = books.parse_response("""<ENVELOPE><HEADER><STATUS>0</STATUS></HEADER><BODY><DATA>
        <STATUS.LIST><STATUS><CODE>123</CODE><DESC>Example company missing</DESC></STATUS></STATUS.LIST>
        </DATA></BODY></ENVELOPE>""")
    assert not result["ok"]
    assert result["raw_status"] == "0"
    assert result["errors"] == ["123: Example company missing"]


def test_export_requests():
    for xml, kind, ident in ((books.export_ledgers_request(CTX.company), "Collection", "Ledger"),
                             (books.export_daybook_request(CTX.company, DAY, DAY), "Data", "Day Book")):
        root = ET.fromstring(xml)
        assert root.findtext("HEADER/TALLYREQUEST") == "Export"
        assert root.findtext("HEADER/TYPE") == kind
        assert root.findtext("HEADER/ID") == ident
        assert root.findtext(".//SVCURRENTCOMPANY") == CTX.company
        assert root.findtext(".//SVEXPORTFORMAT") == "$$SysName:XML"
        if ident == "Day Book":
            assert root.findtext(".//SVFROMDATE") == root.findtext(".//SVTODATE") == "20260402"


@pytest.mark.parametrize("wrapper", ["{}", "<ENVELOPE><BODY><DATA><COLLECTION>{}</COLLECTION></DATA></BODY></ENVELOPE>"])
def test_ledger_export(wrapper):
    xml = '<LEDGER NAME="Example &amp; Supplier"><PARENT>Sundry Creditors</PARENT><PARTYGSTIN>' + gstin("29") + '</PARTYGSTIN></LEDGER>'
    assert books.parse_ledger_export(wrapper.format(xml)) == [dict(name="Example & Supplier", parent="Sundry Creditors", gstin=gstin("29"))]
    assert books.parse_ledger_export("<LEDGER/>") == []
    assert books.parse_ledger_export('<LEDGER><LANGUAGENAME.LIST><NAME.LIST><NAME>Example</NAME></NAME.LIST></LANGUAGENAME.LIST></LEDGER>')[0]["name"] == "Example"


@pytest.mark.parametrize("day", ["20260402", "2026-04-02"])
def test_daybook_export(day):
    xml = f"""<ENVELOPE><VOUCHER VCHTYPE="Sales"><DATE>{day}</DATE><VOUCHERNUMBER>S1</VOUCHERNUMBER>
        <PARTYLEDGERNAME>Example Customer</PARTYLEDGERNAME><ALLLEDGERENTRIES.LIST><LEDGERNAME>Sales</LEDGERNAME>
        <AMOUNT>100</AMOUNT></ALLLEDGERENTRIES.LIST><ALLLEDGERENTRIES.LIST><LEDGERNAME>Example Customer</LEDGERNAME>
        <AMOUNT>-118.00</AMOUNT></ALLLEDGERENTRIES.LIST></VOUCHER><VOUCHER><DATE>bad</DATE></VOUCHER></ENVELOPE>"""
    assert books.parse_daybook_export(xml) == [dict(date="2026-04-02", vtype="Sales", number="S1", party="Example Customer", amount="118.00")]
    assert books.parse_daybook_export(f"<VOUCHER><DATE>{day}</DATE><VOUCHERTYPENAME>Payment</VOUCHERTYPENAME><AMOUNT>2.00</AMOUNT></VOUCHER>")[0]["amount"] == "2.00"


@pytest.mark.parametrize("xml", ["", "garbage", "<broken>", '<!DOCTYPE x [<!ENTITY a "a">]><x/>',
    '<VOUCHER><DATE>20260402</DATE><VOUCHERTYPENAME>Sales</VOUCHERTYPENAME><AMOUNT>NaN</AMOUNT></VOUCHER>'])
def test_bad_exports(xml):
    assert books.parse_ledger_export(xml) == []
    assert books.parse_daybook_export(xml) == []


@pytest.mark.parametrize("state, taxes", [("29", {"Input CGST": "9.01", "Input SGST": "9.00"}),
                                       ("27", {"Input IGST": "18.01"})])
def test_purchase_gst(state, taxes):
    draft = purchase(supplier_gstin=gstin(state))
    assert draft.balanced()
    assert {l.ledger: str(l.amount) for l in draft.lines if l.ledger.startswith("Input")} == taxes
    assert draft.lines[-1] == Line("Example Supplier", Decimal("118.06"), "Cr")
    assert not draft.flags
    assert sum(Decimal(e.text) for e in ET.fromstring(books.voucher_xml("Example", [draft])).iter("AMOUNT")) == 0


def test_sales_and_place_override():
    for state, taxes in (("29", {"Output CGST", "Output SGST"}), ("27", {"Output IGST"})):
        draft = books.sales_draft(CTX, date=DAY, customer="Example Buyer", customer_gstin=gstin("29"),
                                  invoice_no="S-1", taxable="100.05", rate_pct="18", place_of_supply=state)
        assert draft.balanced()
        assert {l.ledger for l in draft.lines if l.ledger.startswith("Output")} == taxes
        assert draft.lines[-1].side == "Dr"
        root = ET.fromstring(books.voucher_xml("Example", [draft]))
        assert root.findtext(".//VOUCHERNUMBER") == "S-1"
        assert root.find(".//REFERENCE") is None


def test_gstin_and_blocked_credit_flags():
    valid = gstin("29")
    invalid = valid[:-1] + ("0" if valid[-1] != "0" else "1")
    assert "GSTIN_INVALID" in purchase(supplier_gstin=invalid).flags
    assert "GSTIN_MISSING" in purchase(supplier_gstin="").flags
    assert "ITC_BLOCKED_17_5" in purchase(purchase_ledger="Food and catering").flags
    assert purchase(supplier_gstin=invalid).balanced()
    assert "GSTIN_INVALID" not in purchase(supplier_gstin=valid.lower()).flags
    assert "GSTIN_INVALID" in purchase(supplier_gstin=123).flags


def test_zero_rate_and_paise_rounding():
    draft = purchase(taxable="10.005", rate_pct="0")
    assert draft.lines == (Line("Purchases", Decimal("10.01"), "Dr"),
                           Line("Example Supplier", Decimal("10.01"), "Cr"))
    assert draft.balanced()
    root = ET.fromstring(books.voucher_xml("Example", [purchase(supplier_gstin="")]))
    assert root.findtext(".//GSTREGISTRATIONTYPE") == "Unregistered/Consumer"


@pytest.mark.parametrize("value", ["bad", "NaN", "Infinity", "-1", "0", "0.001", None])
def test_bad_amounts_return_flags(value):
    draft = purchase(taxable=value)
    assert "INVALID_AMOUNT_OR_RATE" in draft.flags
    assert not draft.lines
    payment = books.payment_draft(CTX, date=DAY, party="Example", amount=value, mode="bank", ledger="Rent Paid", narration="Example")
    assert "INVALID_AMOUNT" in payment.flags
    assert not payment.lines


@pytest.mark.parametrize("rate", ["bad", "NaN", "Infinity", "-1", "101", None])
def test_bad_rate_returns_flag(rate):
    assert "INVALID_AMOUNT_OR_RATE" in purchase(rate_pct=rate).flags


def test_payment_receipt_tds():
    args = dict(date=DAY, party="Example Contractor", amount="40000", mode="bank", ledger="Professional Fees", narration="Example work")
    draft = books.payment_draft(CTX, **args, tds_section="194C")
    assert draft.balanced()
    assert draft.lines == (Line("Professional Fees", Decimal("40000.00"), "Dr"),
                           Line("Bank Account", Decimal("39200.00"), "Cr"),
                           Line("TDS Payable - 194C", Decimal("800.00"), "Cr"))
    for mode in ("bank", "cash"):
        for build in (books.payment_draft, books.receipt_draft):
            draft = build(CTX, **dict(args, mode=mode))
            assert draft.balanced()
            cash_line = draft.lines[1]
            assert cash_line.ledger == ("Bank Account" if mode == "bank" else "Cash")
            assert cash_line.side == ("Cr" if build == books.payment_draft else "Dr")
            root = ET.fromstring(books.voucher_xml(CTX.company, [draft]))
            assert sum(Decimal(e.text) for e in root.iter("AMOUNT")) == 0
    assert books.payment_draft(CTX, **dict(args, mode="card")).flags == ("INVALID_MODE",)
    assert books.payment_draft(CTX, **args, tds_section="unsupported").flags == ("TDS_SECTION_UNSUPPORTED",)
    assert len(books.payment_draft(CTX, **dict(args, amount="10"), tds_section="194C").lines) == 2


@pytest.mark.parametrize("section", ["194C", "194J", "194H", "194Q"])
def test_supported_tds_sections_balance(section):
    draft = books.payment_draft(CTX, date=DAY, party="Example Payee", amount="6000000.01", mode="bank",
                                ledger="Example Payee", narration="Example settlement", tds_section=section)
    assert draft.balanced()
    assert draft.lines[-1].ledger == "TDS Payable - " + section
    assert draft.lines[-1].amount > 0


def test_custom_cash_and_bank_ledgers():
    ctx = BookContext(bank_ledger="Example Bank", cash_ledger="Example Till")
    for mode, ledger in (("bank", "Example Bank"), ("cash", "Example Till")):
        draft = books.receipt_draft(ctx, date=DAY, party="Example Buyer", amount="5.01", mode=mode,
                                    ledger="Example Buyer", narration="Example receipt")
        assert draft.lines[1] == Line(ledger, Decimal("5.01"), "Dr")


def test_daybook_skips_bad_items_without_losing_good_ones():
    def voucher(day="20260402", amount="10.00"):
        return f'<VOUCHER><DATE>{day}</DATE><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME><AMOUNT>{amount}</AMOUNT></VOUCHER>'
    xml = "<ENVELOPE>" + voucher(day="20260230") + voucher(amount="garbage") + voucher(amount="Infinity") + voucher() + "</ENVELOPE>"
    assert books.parse_daybook_export(xml) == [dict(date="2026-04-02", vtype="Receipt", number="", party="", amount="10.00")]
