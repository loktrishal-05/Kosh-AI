"""mcp-server-gstn-nic (Mock sandbox). Read-only portal data + STAGING tools. There is deliberately no RETFILE/IMS-reject tool.
ponytail: fixtures stand in for the GSP/NIC sandbox; Live mode swaps `profiles`/`gstr2b` for authenticated GSP calls (Phase 7)."""
from datetime import datetime
from decimal import Decimal

from taxsetu_engine import ewb, gst

from . import statutory_rag as rag
from .core import Server, ToolError


def build(stage=None, profiles: dict | None = None, gstr2b: dict | None = None) -> Server:
    """stage(tenant_id, kind, payload) -> dict is HitlGate.agent_tools.stage; None = nowhere to stage, staging tools refuse."""
    s, profiles, gstr2b = Server("mcp-server-gstn-nic"), profiles or {}, gstr2b or {}

    def _stage(tenant_id, kind, payload):
        if stage is None:
            raise ToolError("no staging gateway configured")
        return stage(tenant_id, kind, payload)

    @s.resource("gst://taxpayer/{gstin}/public-profile")
    def profile(gstin):
        if not gst.is_valid_gstin(gstin):
            raise ToolError("invalid GSTIN checksum")
        return profiles.get(gstin, {"gstin": gstin, "status": "UNKNOWN", "filings": []})

    @s.resource("gst://returns/{gstin}/{period}/gstr2b")
    def r2b(gstin, period):
        return gstr2b.get((gstin, period), [])

    @s.tool
    def stage_gstr1_or_3b_retsave(tenant_id: str, gstin: str, period: str, return_type: str, json_body: dict) -> dict:
        """Stage (RETSAVE) a GSTR-1 or GSTR-3B draft. A human must authorize filing; this tool cannot."""
        if return_type not in ("GSTR1", "GSTR3B"):
            raise ToolError("return_type must be GSTR1 or GSTR3B")
        return _stage(tenant_id, return_type, {"gstin": gstin, "period": period, **json_body})

    @s.tool(hitl=True)
    def generate_eway_bill_v103(tenant_id: str, gstin: str, vehicle_no: str, distance_km: int, consignment_value: str,
                                interstate: bool = False) -> dict:
        """Draft an EWB-01 (staged for one-tap human approval). Returns validity and the 4-hour pre-expiry alert time."""
        if not gst.is_valid_gstin(gstin):
            raise ToolError("invalid GSTIN checksum")
        if not ewb.ewb_required(Decimal(consignment_value), interstate):
            return {"required": False}
        valid = ewb.ewb_valid_until(datetime.now(), distance_km)
        d = _stage(tenant_id, "EWB", {"gstin": gstin, "vehicle_no": vehicle_no, "distance_km": str(distance_km),
                                      "valid_until": valid.isoformat()})
        return {"required": True, "valid_until": valid, "alert_at": ewb.expiry_alert_time(valid), **d}

    @s.tool(hitl=True)
    def extend_or_update_ewb_part_b(tenant_id: str, gstin: str, ewb_no: str, vehicle_no: str, valid_until: str, reason: str,
                                    now: str = "") -> dict:
        """Stage a Part-B/validity update; refused outside the +/-8h extension window around expiry."""
        lo, hi = ewb.extension_window(datetime.fromisoformat(valid_until))
        t = datetime.fromisoformat(now) if now else datetime.now()
        if not lo <= t <= hi:
            raise ToolError(f"extension only allowed between {lo} and {hi}")
        return _stage(tenant_id, "EWB", {"gstin": gstin, "vehicle_no": vehicle_no, "ewb_no": ewb_no, "reason": reason})

    @s.tool(hitl=True)
    def draft_mov07_circular_64_38_reply(defect: str, valid_invoice_on_file: bool, tax_payable: str, declared_vehicle: str = "",
                                         actual_vehicle: str = "", on_date: str = "") -> dict:
        """Reply letter text. Circular 64/38 is cited only when the deterministic gate allows it AND the citation resolves in the RAG corpus."""
        v = ewb.classify_mov07(defect, valid_invoice_on_file, Decimal(tax_payable), declared=declared_vehicle, actual=actual_vehicle)
        on = on_date or datetime.now().date().isoformat()
        if v.circular_64_38_applies:
            cite = rag.effective("CBIC-64/38/2018-GST", datetime.fromisoformat(on).date())
            body = (f"Defect '{defect}' is a clerical error; a valid tax invoice is on file and tax is paid. "
                    f"Relief sought under {cite['id']}: penalty limited to Rs 1,000 ({v.basis}).")
        else:
            cite = None
            body = f"Not eligible for Circular 64/38 relief ({v.reason}). Exposure: Rs {v.penalty} under {v.basis}. Escalate to CA."
        return {"circular_applies": v.circular_64_38_applies, "penalty": v.penalty, "citation": cite and cite["id"], "letter": body}
    return s
