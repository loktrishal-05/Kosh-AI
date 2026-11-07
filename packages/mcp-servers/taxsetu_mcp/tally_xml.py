"""mcp-server-tally-xml: validates and posts voucher XML to TallyPrime's HTTP port 9000.
ponytail: XML shapes follow Tally's import format but are UNVERIFIED against a live TallyPrime; default transport is a dry run."""
import xml.etree.ElementTree as ET
from decimal import Decimal

from taxsetu_engine import gst

from .core import Server, ToolError


def dry_run(xml: str) -> str:
    return "<RESPONSE><CREATED>0</CREATED><DRYRUN>1</DRYRUN></RESPONSE>"


def build(post=dry_run, masters: list | None = None) -> Server:
    """post(xml) -> response xml. Real wiring: urllib POST to http://localhost:9000."""
    s, masters, daybook = Server("mcp-server-tally-xml"), masters if masters is not None else [], []

    @s.tool(hitl=True)
    def post_tally_voucher(voucher_type: str, xml_payload: str) -> dict:
        """Push a voucher into Tally. Must be well-formed and double-entry balanced (amounts net to zero)."""
        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as e:
            raise ToolError(f"malformed XML: {e}") from e
        if root.tag != "ENVELOPE" or (v := root.find(".//VOUCHER")) is None:
            raise ToolError("not a Tally ENVELOPE/VOUCHER document")
        if sum((Decimal(a.text) for a in root.iter("AMOUNT")), Decimal(0)) != 0:
            raise ToolError("voucher does not balance")
        resp = post(xml_payload)
        daybook.append({"type": voucher_type, "no": v.findtext("VOUCHERNUMBER"), "date": v.findtext("DATE")})
        return {"posted": True, "tally_response": resp}

    @s.tool(hitl=True)
    def create_party_ledger(gstin: str, name: str, state: str) -> dict:
        """Auto-create a missing vendor ledger under Sundry Creditors (idempotent on GSTIN)."""
        if not gst.is_valid_gstin(gstin):
            raise ToolError("invalid GSTIN checksum")
        if any(m["gstin"] == gstin for m in masters):
            return {"created": False, "reason": "exists"}
        e = ET.Element("ENVELOPE")
        lg = ET.SubElement(ET.SubElement(ET.SubElement(ET.SubElement(ET.SubElement(e, "BODY"), "IMPORTDATA"), "REQUESTDATA"),
                                         "TALLYMESSAGE"), "LEDGER", {"NAME": name, "ACTION": "Create"})
        for tag, val in (("PARENT", "Sundry Creditors"), ("PARTYGSTIN", gstin), ("LEDSTATENAME", state)):
            ET.SubElement(lg, tag).text = val
        resp = post(ET.tostring(e, encoding="unicode"))
        masters.append({"gstin": gstin, "name": name, "state": state})
        return {"created": True, "tally_response": resp}

    @s.resource("tally://company/active/masters")
    def m():
        return masters

    @s.resource("tally://company/active/daybook/{date}")
    def d(date):
        return [v for v in daybook if v["date"] == date.replace("-", "")]
    return s
