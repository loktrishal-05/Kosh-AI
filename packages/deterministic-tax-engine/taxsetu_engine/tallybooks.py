"""Draft books entries and Tally XML. No posting or I/O."""
import re
import xml.etree.ElementTree as ET
from datetime import date as Date, datetime
from decimal import Decimal, InvalidOperation

from . import gst, tds
from .money import d, r2
from .tally_models import Line, VoucherDraft


GST_STATES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
    "24": "Gujarat", "25": "Daman & Diu", "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra", "28": "Andhra Pradesh", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory", "99": "Other Country",
}
_INVALID_XML = re.compile("[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _clean(value):
    return _INVALID_XML.sub("", str(value))


def _text(parent, tag, value):
    ET.SubElement(parent, tag).text = _clean(value)


def _opt(parent, tag, value):
    """Like _text but leaves the tag out when there is nothing to say (Tally treats an empty GST tag as a value)."""
    if value not in ("", None):
        _text(parent, tag, value)


def _envelope(company, request, kind, ident):
    env = ET.Element("ENVELOPE")
    header = ET.SubElement(env, "HEADER")
    for tag, value in (("VERSION", "1"), ("TALLYREQUEST", request), ("TYPE", kind), ("ID", ident)):
        _text(header, tag, value)
    body = ET.SubElement(env, "BODY")
    desc = ET.SubElement(body, "DESC")
    variables = ET.SubElement(desc, "STATICVARIABLES")
    _text(variables, "SVCURRENTCOMPANY", company)
    return env, body, desc, variables


def _import_envelope(company, report):
    """The classic import shape every Tally.ERP 9 / TallyPrime accepts: HEADER Import Data, BODY/IMPORTDATA/REQUESTDESC + REQUESTDATA."""
    env = ET.Element("ENVELOPE")
    _text(ET.SubElement(env, "HEADER"), "TALLYREQUEST", "Import Data")
    imp = ET.SubElement(ET.SubElement(env, "BODY"), "IMPORTDATA")
    desc = ET.SubElement(imp, "REQUESTDESC")
    _text(desc, "REPORTNAME", report)
    _text(ET.SubElement(desc, "STATICVARIABLES"), "SVCURRENTCOMPANY", company)
    return env, ET.SubElement(imp, "REQUESTDATA")


def voucher_xml(company: str, drafts: list) -> str:
    """Serialize balanced drafts using Tally's debit-negative convention."""
    env, data = _import_envelope(company, "Vouchers")
    for draft in drafts:
        if not draft.lines or any(l.side not in ("Dr", "Cr") or not l.amount.is_finite()
                                  or l.amount <= 0 or l.amount != r2(l.amount) for l in draft.lines):
            raise ValueError("draft needs positive, finite paise lines with Dr/Cr sides")
        if not draft.balanced():
            raise ValueError("draft is not balanced")
        msg = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        v = ET.SubElement(msg, "VOUCHER", {"VCHTYPE": _clean(draft.vtype), "ACTION": "Create",
                                         "OBJVIEW": "Accounting Voucher View"})
        for tag, value in (("DATE", draft.date.strftime("%Y%m%d")),
                           ("EFFECTIVEDATE", draft.date.strftime("%Y%m%d")),
                           ("VOUCHERTYPENAME", draft.vtype)):
            _text(v, tag, value)
        if draft.number:
            _text(v, "VOUCHERNUMBER", draft.number)
        if draft.vtype == "Purchase":
            _text(v, "REFERENCE", draft.reference)
            _text(v, "REFERENCEDATE", (draft.reference_date or draft.date).strftime("%Y%m%d"))
        trade = draft.vtype in ("Sales", "Purchase")
        _opt(v, "PARTYLEDGERNAME", draft.party)
        if trade:
            _opt(v, "PARTYGSTIN", draft.party_gstin)
            _opt(v, "PLACEOFSUPPLY", GST_STATES.get(draft.place_of_supply, draft.place_of_supply))
            _text(v, "GSTREGISTRATIONTYPE", "Regular" if draft.party_gstin else "Unregistered/Consumer")
        _opt(v, "NARRATION", _clean(draft.narration)[:250])
        for line in draft.lines:
            entry = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            _text(entry, "LEDGERNAME", line.ledger)
            _text(entry, "ISDEEMEDPOSITIVE", "Yes" if line.side == "Dr" else "No")
            _text(entry, "AMOUNT", format(-line.amount if line.side == "Dr" else line.amount, ".2f"))
    return ET.tostring(env, encoding="unicode")


def masters_xml(company: str, ledgers: list) -> str:
    """Serialize ledger masters, keeping the first of each name."""
    env, data = _import_envelope(company, "All Masters")
    seen = set()
    for spec in ledgers:
        name = _clean(spec.name)
        if name in seen:
            continue
        seen.add(name)
        msg = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        ledger = ET.SubElement(msg, "LEDGER", {"NAME": name, "ACTION": "Create"})
        parent = "Duties & Taxes" if spec.gst_duty_head else spec.parent
        party = parent in ("Sundry Debtors", "Sundry Creditors")
        _text(ledger, "PARENT", parent)
        _text(ledger, "ISBILLWISEON", "Yes" if party else "No")
        if party:
            _opt(ledger, "PARTYGSTIN", spec.gstin)
            _opt(ledger, "LEDSTATENAME", GST_STATES.get(spec.state, spec.state))
            _text(ledger, "GSTREGISTRATIONTYPE", spec.gst_registration_type or ("Regular" if spec.gstin else "Unregistered/Consumer"))
        if spec.gst_duty_head:
            _text(ledger, "TAXTYPE", "GST")
            _text(ledger, "GSTDUTYHEAD", spec.gst_duty_head)
    return ET.tostring(env, encoding="unicode")


def _parse(xml):
    if not isinstance(xml, str) or not xml.strip():
        raise ValueError("Empty XML response")
    if re.search(r"DOCTYPE|ENTITY", xml, re.I):
        raise ValueError("DOCTYPE and ENTITY are forbidden")
    return ET.fromstring(xml)


def parse_response(xml: str) -> dict:
    """Read success counters or a failure envelope without trusting XML."""
    result = {"ok": False, "created": 0, "altered": 0, "errors": [], "raw_status": ""}
    try:
        root = _parse(xml)
        status = root.findtext("./HEADER/STATUS", "").strip()
        result["raw_status"] = status
        counters = {}
        for tag in ("CREATED", "ALTERED", "DELETED", "IGNORED", "ERRORS", "CANCELLED", "EXCEPTIONS"):
            value = root.findtext(".//" + tag, "0").strip()
            count = int(value)
            if count < 0:
                raise ValueError("Negative import counter")
            counters[tag] = count
        result.update(created=counters["CREATED"], altered=counters["ALTERED"])
        result["errors"] = [(e.text or "Tally line error").strip() or "Tally line error"
                            for e in root.iter("LINEERROR")]
        for tag in ("ERRORS", "EXCEPTIONS"):
            if counters[tag]:
                result["errors"].append(f"Tally {tag.lower()}: {counters[tag]}")
        if status == "0":
            code = root.findtext(".//STATUS.LIST/STATUS/CODE", "").strip()
            desc = root.findtext(".//STATUS.LIST/STATUS/DESC", "Import failed").strip()
            result["errors"].append(f"{code}: {desc}" if code else desc)
        result["ok"] = status != "0" and not result["errors"] and result["created"] + result["altered"] > 0
        if not result["ok"] and not result["errors"]:
            result["errors"].append("No vouchers or masters created or altered")
    except (ET.ParseError, ValueError, TypeError) as exc:
        result["errors"].append(str(exc))
    return result


def export_ledgers_request(company):
    env, _, _, variables = _envelope(company, "Export", "Data", "List of Accounts")
    _text(variables, "SVEXPORTFORMAT", "$$SysName:XML")
    _text(variables, "ACCOUNTTYPE", "Ledgers")
    return ET.tostring(env, encoding="unicode")


def export_daybook_request(company, start: Date, end: Date):
    env, _, _, variables = _envelope(company, "Export", "Data", "Day Book")
    for tag, value in (("SVEXPORTFORMAT", "$$SysName:XML"), ("SVFROMDATE", start.strftime("%Y%m%d")),
                       ("SVTODATE", end.strftime("%Y%m%d"))):
        _text(variables, tag, value)
    return ET.tostring(env, encoding="unicode")


def parse_ledger_export(xml) -> list:
    """Read flat or nested ledger collections; ignore unnamed entries."""
    try:
        root = _parse(xml)
    except (ET.ParseError, ValueError, TypeError):
        return []
    result = []
    for ledger in root.iter("LEDGER"):
        name = (ledger.get("NAME") or ledger.findtext(".//NAME", "")).strip()
        if name:
            result.append({"name": name, "parent": ledger.findtext(".//PARENT", "").strip(),
                           "gstin": ledger.findtext(".//PARTYGSTIN", "").strip()})
    return result


def parse_daybook_export(xml) -> list:
    """Read voucher summaries; use the party entry when no total is present."""
    try:
        root = _parse(xml)
    except (ET.ParseError, ValueError, TypeError):
        return []
    result = []
    for voucher in root.iter("VOUCHER"):
        try:
            day_text = voucher.findtext(".//DATE", "").strip()
            day = (datetime.strptime(day_text, "%Y%m%d").date() if len(day_text) == 8
                   else Date.fromisoformat(day_text))
            vtype = voucher.findtext(".//VOUCHERTYPENAME") or voucher.get("VCHTYPE", "")
            party = voucher.findtext(".//PARTYLEDGERNAME", "").strip()
            amount = voucher.findtext("AMOUNT")
            if amount is None:
                entries = voucher.findall(".//ALLLEDGERENTRIES.LIST") + voucher.findall(".//LEDGERENTRIES.LIST")
                entry = next((e for e in entries if e.findtext("LEDGERNAME") == party
                              or e.findtext("ISPARTYLEDGER", "").lower() == "yes"), None)
                amount = entry.findtext("AMOUNT") if entry is not None else None
                if not entries:
                    amount = voucher.findtext(".//AMOUNT")
            value = d(amount)
            if not value.is_finite() or not vtype:
                continue
            result.append({"date": day.isoformat(), "vtype": vtype,
                           "number": voucher.findtext(".//VOUCHERNUMBER", "").strip(),
                           "party": party, "amount": format(abs(value), "f")})
        except (ValueError, TypeError, InvalidOperation):
            continue
    return result


def _amount(value):
    amount = d(value)
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Invalid amount")
    amount = r2(amount)
    if not amount:
        raise ValueError("Amount rounds to zero")
    return amount


def _trade_draft(ctx, day, party, gstin, invoice_no, taxable, rate_pct, ledger, purchase, number="", place=""):
    gstin = str(gstin or "").strip().upper()
    flags = []
    if not gstin:
        flags.append("GSTIN_MISSING")
    elif not gst.is_valid_gstin(gstin):
        flags.append("GSTIN_INVALID")
    party_state = gstin[:2] if gst.is_valid_gstin(gstin) else ctx.state_code
    state = ctx.state_code if purchase else (place or party_state)      # a purchase is delivered to us; a sale goes to the customer's state
    if purchase and gst.blocked_credit_17_5(description=ledger):
        flags.append("ITC_BLOCKED_17_5")
    lines = []
    try:
        base, rate = _amount(taxable), d(rate_pct)
        if not rate.is_finite() or rate < 0 or rate > 100:
            raise ValueError("Invalid GST rate")
        split = gst.split_gst(base, rate, party_state, state) if purchase else gst.split_gst(base, rate, ctx.state_code, state)
        side, other = ("Dr", "Cr") if purchase else ("Cr", "Dr")
        lines.append(Line(ledger, base, side))
        for tax, amount in (("CGST", split.cgst), ("SGST", split.sgst), ("IGST", split.igst)):
            if amount:
                lines.append(Line(("Input " if purchase else "Output ") + tax, amount, side))
        lines.append(Line(party, split.invoice_total, other))
    except (ValueError, TypeError, InvalidOperation):
        flags.append("INVALID_AMOUNT_OR_RATE")
    return VoucherDraft("Purchase" if purchase else "Sales", day, tuple(lines), number=number, party=party,
                        reference=invoice_no, reference_date=day, party_gstin=gstin, place_of_supply=state,
                        flags=tuple(flags))


def purchase_draft(ctx, *, date, supplier, supplier_gstin, invoice_no, taxable, rate_pct,
                   purchase_ledger="Purchases", number=""):
    return _trade_draft(ctx, date, supplier, supplier_gstin, invoice_no, taxable, rate_pct, purchase_ledger, True, number)


def sales_draft(ctx, *, date, customer, customer_gstin, invoice_no, taxable, rate_pct,
                sales_ledger="Sales", place_of_supply=""):
    return _trade_draft(ctx, date, customer, customer_gstin, invoice_no, taxable, rate_pct, sales_ledger, False,
                        number=invoice_no, place=place_of_supply)


def payment_draft(ctx, *, date, party, amount, mode, ledger, narration, tds_section=None):
    """Debit the selected ledger and pay the balance through bank or cash."""
    flags, lines = [], []
    if mode not in ("bank", "cash"):
        flags.append("INVALID_MODE")
    try:
        total = _amount(amount)
        tax = tds.compute_tds(tds_section, total).tds if tds_section else Decimal(0)
        if not flags:
            lines.append(Line(ledger, total, "Dr"))
            if total > tax:
                lines.append(Line(ctx.bank_ledger if mode == "bank" else ctx.cash_ledger, total - tax, "Cr"))
            if tax:
                lines.append(Line("TDS Payable - " + tds_section, tax, "Cr"))
    except KeyError:
        flags.append("TDS_SECTION_UNSUPPORTED")
    except (ValueError, TypeError, InvalidOperation):
        flags.append("INVALID_AMOUNT")
    return VoucherDraft("Payment", date, tuple(lines), party=party, narration=narration, flags=tuple(flags))


def receipt_draft(ctx, *, date, party, amount, mode, ledger, narration):
    """Receive bank or cash against the selected ledger."""
    payment = payment_draft(ctx, date=date, party=party, amount=amount, mode=mode, ledger=ledger, narration=narration)
    return VoucherDraft("Receipt", date, tuple(Line(l.ledger, l.amount, "Cr" if l.side == "Dr" else "Dr")
                                               for l in payment.lines),
                        party=party, narration=narration, flags=payment.flags)
