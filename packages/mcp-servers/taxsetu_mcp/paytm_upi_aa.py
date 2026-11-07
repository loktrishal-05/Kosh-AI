"""mcp-server-paytm-upi-aa (mock). Payment tools only create an INTENT; the owner's own UPI PIN moves money (never the agent)."""
import uuid

from taxsetu_engine import payments

from .core import Server, ToolError


def build(statements: dict | None = None) -> Server:
    s, escrows, statements = Server("mcp-server-paytm-upi-aa"), {}, statements or {}

    @s.tool(hitl=True)
    def execute_split_vendor_payout(inv_id: str, taxable: str, gst: str, trust_score: int, tds_section: str = "") -> dict:
        """3-way split (net base / TDS / GST escrow). Amounts are computed here from the engine, never taken from the caller."""
        sp = payments.split_payment(taxable, gst, trust_score, tds_section or None)
        eid = None
        if sp.gst_escrow:
            eid = str(uuid.uuid4())
            escrows[eid] = {"inv_id": inv_id, "amount": sp.gst_escrow, "state": "HELD"}
        return {"status": "INTENT_CREATED_AWAITING_OWNER_UPI_PIN", "base_payout": sp.base_payout, "tds": sp.tds,
                "gst_escrow": sp.gst_escrow, "gst_paid_direct": sp.gst_paid_direct, "escrow_id": eid}

    @s.tool
    def release_or_refund_gst_escrow(escrow_id: str, gstr2b_matched: bool) -> dict:
        """Matched in GSTR-2B -> release to vendor; otherwise refund to the buyer. Terminal: a settled escrow cannot be flipped."""
        e = escrows.get(escrow_id)
        if e is None:
            raise ToolError("unknown escrow")
        if e["state"] != "HELD":
            raise ToolError(f"escrow already {e['state']}")
        e["state"] = "RELEASED" if gstr2b_matched else "REFUNDED"
        return {"escrow_id": escrow_id, "state": e["state"], "amount": e["amount"]}

    @s.tool
    def generate_smart_compliance_receipt(utr: str, inv_id: str, taxable: str, gst: str, trust_score: int, tds_section: str = "") -> dict:
        """ponytail: partial receipt (split + balanced ledger rows); the full 22-field receipt is still to do."""
        sp = payments.split_payment(taxable, gst, trust_score, tds_section or None)
        return {"utr": utr, "inv_id": inv_id, "split": sp.__dict__, "ledger": payments.purchase_ledger_entries(taxable, gst, sp)}

    @s.resource("bank://aa/{pan}/statements/{month}")
    def stmt(pan, month):
        return statements.get((pan, month), [])

    @s.resource("escrow://gst-holds/active")
    def holds():
        return {k: v for k, v in escrows.items() if v["state"] == "HELD"}
    return s
