"""TallyPrime XML voucher serializer (import over HTTP port 9000). Structure follows Tally's ENVELOPE/IMPORTDATA format.
ponytail: not yet verified against a live TallyPrime instance - validate once on a real install before the demo."""
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

from .money import r2


def purchase_voucher_xml(company: str, vendor: str, inv_no: str, inv_date: date, lines: list) -> str:
    """lines: [(ledger_name, debit, credit)]. Tally convention: debit = negative amount + ISDEEMEDPOSITIVE Yes."""
    env = ET.Element("ENVELOPE")
    h = ET.SubElement(env, "HEADER")
    ET.SubElement(h, "TALLYREQUEST").text = "Import Data"
    body = ET.SubElement(env, "BODY")
    imp = ET.SubElement(body, "IMPORTDATA")
    req = ET.SubElement(imp, "REQUESTDESC")
    ET.SubElement(req, "REPORTNAME").text = "Vouchers"
    ET.SubElement(ET.SubElement(req, "STATICVARIABLES"), "SVCURRENTCOMPANY").text = company
    msg = ET.SubElement(ET.SubElement(imp, "REQUESTDATA"), "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
    v = ET.SubElement(msg, "VOUCHER", {"VCHTYPE": "Purchase", "ACTION": "Create"})
    ET.SubElement(v, "DATE").text = inv_date.strftime("%Y%m%d")
    ET.SubElement(v, "VOUCHERTYPENAME").text = "Purchase"
    ET.SubElement(v, "VOUCHERNUMBER").text = inv_no
    ET.SubElement(v, "PARTYLEDGERNAME").text = vendor
    for name, dr, cr in lines:
        e = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(e, "LEDGERNAME").text = name
        is_debit = r2(dr) > 0
        ET.SubElement(e, "ISDEEMEDPOSITIVE").text = "Yes" if is_debit else "No"
        ET.SubElement(e, "AMOUNT").text = format(-r2(dr) if is_debit else r2(cr), "f")
    return ET.tostring(env, encoding="unicode")
