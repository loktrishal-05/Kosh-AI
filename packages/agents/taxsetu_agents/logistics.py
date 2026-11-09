"""Agent 3: e-Way Bill generation and checkpoint defence. OCR output (vehicle number) is untrusted and validated; the Circular 64/38 cite
is produced by the gstn-nic tool only after the deterministic gate AND a RAG citation lookup both pass. Staging only; a human approves."""
import re

from taxsetu_engine import gst, planner, recon

from .graph import Graph
from .ingestion import dedup_hash, fy_of

VEHICLE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}$")     # e.g. TN09BC4411, DL1CAB1234


def clean_vehicle(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw.upper())


class LogisticsAgent:
    def __init__(self, client, seen: set | None = None):
        self.c, self.seen = client, seen if seen is not None else set()
        g = self.g = Graph()
        g.node("check", lambda s: "generate" if s["mode"] == "GENERATE" else "defend")(self.check)
        g.node("generate")(self.generate)
        g.node("defend")(self.defend)

    def run_generate(self, tenant_id: str, driver_phone: str, gstin: str, invoice_no: str, invoice_date, vehicle_ocr: str,
                     distance_km: int, consignment_value: str, interstate: bool = False) -> dict:
        return self.g.run("check", dict(mode="GENERATE", tenant_id=tenant_id, phone=driver_phone, gstin=gstin, inv_no=invoice_no,
                                        inv_date=invoice_date, vehicle=clean_vehicle(vehicle_ocr), km=distance_km,
                                        value=consignment_value, interstate=interstate))

    def run_defend(self, tenant_id: str, owner_phone: str, defect: str, valid_invoice_on_file: bool, tax_payable: str,
                   declared_vehicle: str = "", actual_vehicle: str = "", on_date: str = "") -> dict:
        return self.g.run("check", dict(mode="DEFEND", tenant_id=tenant_id, phone=owner_phone, defect=defect,
                                        valid=valid_invoice_on_file, tax=tax_payable, declared=declared_vehicle,
                                        actual=actual_vehicle, on_date=on_date))

    def check(self, s):
        if s["mode"] != "GENERATE":
            return
        if not gst.is_valid_gstin(s["gstin"]):
            s.update(status="NEEDS_REVIEW", errors=["GSTIN fails checksum"], halt=True)
        elif not VEHICLE.match(s["vehicle"]):
            s.update(status="NEEDS_REVIEW", errors=[f"vehicle number '{s['vehicle']}' unreadable - ask driver to confirm"], halt=True)
        elif (b := self._blocked_138e(s["gstin"]))["blocked"]:     # the portal would refuse Part A anyway; say why, up front
            s.update(status="BLOCKED_138E", errors=b["reasons"], halt=True)
        else:
            h = dedup_hash(s["gstin"], s["inv_no"], fy_of(s["inv_date"]))   # clerk + driver both photographed the same invoice
            if h in self.seen:
                s.update(status="DUPLICATE", halt=True)
            else:
                self.seen.add(h)

    def _blocked_138e(self, gstin: str) -> dict:
        """Consignor-side Rule 138E check from GSTN filing history. ponytail: consignee filings are not available to this agent yet."""
        filings = self.c.read("gstn-nic", f"gst://taxpayer/{gstin}/public-profile").get("filings", [])
        return planner.ewb_block_status({"GSTR1": [bool(a) for a, _ in filings], "GSTR3B": [bool(b) for _, b in filings]}, {})

    def generate(self, s):
        r = self.c.call("gstn-nic", "generate_eway_bill_v103", tenant_id=s["tenant_id"], gstin=s["gstin"], vehicle_no=s["vehicle"],
                        distance_km=s["km"], consignment_value=s["value"], interstate=s["interstate"])
        s["result"] = r
        if not r["required"]:
            s["status"] = "NOT_REQUIRED"
            return
        self.c.call("whatsapp-voice", "send_interactive_approval_card", to=s["phone"], buttons=["Approve EWB", "Edit", "Cancel"],
                    summary=f"EWB draft for {s['vehicle']}, valid until {r['valid_until']:%d-%b %H:%M}. Reply to approve.")
        s["status"] = "STAGED"

    def defend(self, s):
        r = self.c.call("gstn-nic", "draft_mov07_circular_64_38_reply", defect=s["defect"], valid_invoice_on_file=s["valid"],
                        tax_payable=s["tax"], declared_vehicle=s["declared"], actual_vehicle=s["actual"], on_date=s["on_date"])
        s["result"] = r
        s["status"] = "REPLY_DRAFTED" if r["circular_applies"] else "ESCALATE_CA"
        self.c.call("whatsapp-voice", "send_interactive_approval_card", to=s["phone"],
                    buttons=["Send reply"] if r["circular_applies"] else ["Call CA"], summary=r["letter"])
