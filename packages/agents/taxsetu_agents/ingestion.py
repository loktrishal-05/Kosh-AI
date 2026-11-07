"""Agent 1: WhatsApp bill -> validated invoice -> supplier trust check -> ITC/TDS/split proposal for the owner's one-tap approval.
The LLM extracts; everything after `validate` is deterministic. It never moves money: it sends an approval card, nothing more."""
import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation

from taxsetu_engine import gst, payments, recon
from taxsetu_engine.tds import compute_tds

from .graph import Graph


def fy_of(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def dedup_hash(gstin: str, inv_no: str, fy: str) -> str:
    return hashlib.sha256(f"{gstin}|{recon.norm_inv(inv_no)}|{fy}".encode()).hexdigest()


class IngestionAgent:
    def __init__(self, client, llm, seen: set | None = None):
        self.c, self.llm, self.seen = client, llm, seen if seen is not None else set()
        g = self.g = Graph()
        g.node("extract", "validate")(lambda s: s.update(raw=self.llm.extract_invoice(s["text"])))
        g.node("validate", "dedup")(self.validate)
        g.node("dedup", "verify_supplier")(self.dedup)
        g.node("verify_supplier", "classify")(self.verify_supplier)
        g.node("classify", "propose")(self.classify)
        g.node("propose")(self.propose)

    def run(self, tenant_id: str, owner_phone: str, text: str, buyer_state: str, tds_section: str | None = None,
            cumulative_paid=0, payee_individual: bool = False) -> dict:
        return self.g.run("extract", dict(tenant_id=tenant_id, owner_phone=owner_phone, text=text, buyer_state=buyer_state,
                                          tds_section=tds_section, cumulative_paid=cumulative_paid, payee_individual=payee_individual,
                                          alerts=[]))

    def validate(self, s):
        r, errs = s["raw"], []
        if not gst.is_valid_gstin(r.get("supplier_gstin", "")):
            errs.append("supplier GSTIN missing or fails checksum")
        if not r.get("invoice_no"):
            errs.append("invoice number missing")
        try:
            inv = dict(gstin=r["supplier_gstin"], no=r["invoice_no"], date=date.fromisoformat(r["invoice_date"]),
                       taxable=Decimal(r["taxable"]), rate=Decimal(r["rate"]), hsn=r.get("hsn", ""), desc=r.get("description", ""))
            if inv["taxable"] <= 0 or not 0 <= inv["rate"] <= 40:
                errs.append("taxable value or GST rate out of range")
        except (KeyError, ValueError, InvalidOperation):
            errs.append("date/amount/rate missing or unreadable")
        if errs:
            s.update(status="NEEDS_REVIEW", errors=errs, halt=True)    # never guess: ask the human to re-send / correct
        else:
            s["inv"] = inv

    def dedup(self, s):
        i = s["inv"]
        h = s["dedup_hash"] = dedup_hash(i["gstin"], i["no"], fy_of(i["date"]))
        if h in self.seen:
            s.update(status="DUPLICATE", halt=True)
        else:
            self.seen.add(h)

    def verify_supplier(self, s):
        p = self.c.read("gstn-nic", f"gst://taxpayer/{s['inv']['gstin']}/public-profile")
        active = p["status"] == "ACTIVE"
        months = [tuple(f) for f in p.get("filings", [])][-6:]
        s["trust_score"] = payments.supplier_trust_score(months, active)
        if p["status"] == "UNKNOWN":
            s["alerts"].append("Supplier not found in GSTN data - verify before paying")
        elif not active:
            s["alerts"].append(f"Supplier GSTIN is {p['status']} - do not pay, ITC will not be available")
        elif any(not (a and b) for a, b in months[-2:]):
            s["alerts"].append("Supplier missed a recent GSTR-1/3B - GST will be held in escrow")

    def classify(self, s):
        i = s["inv"]
        i["split"] = gst.split_gst(i["taxable"], i["rate"], i["gstin"][:2], s["buyer_state"])
        i["blocked"] = gst.blocked_credit_17_5(i["hsn"], i["desc"])
        if i["blocked"]:
            s["alerts"].append(f"ITC blocked under Sec 17(5): {i['blocked']}")
        s["tds"] = None
        if s["tds_section"]:
            s["tds"] = compute_tds(s["tds_section"], i["split"].invoice_total, s["cumulative_paid"],
                                   payee_individual_or_huf=s["payee_individual"], gst_in_amount=i["split"].total_tax)
            if s["tds"].applicable:
                s["alerts"].append(f"Deduct TDS u/s {s['tds_section']}: Rs {s['tds'].tds}")

    def propose(self, s):
        i = s["inv"]
        sp = payments.split_payment(i["taxable"], i["split"].total_tax, s["trust_score"], s["tds_section"],
                                    s["cumulative_paid"], payee_individual_or_huf=s["payee_individual"])
        s["split"] = sp
        s["ledger"] = payments.purchase_ledger_entries(i["taxable"], i["split"].total_tax, sp, bool(i["blocked"]))
        summary = (f"Bill {i['no']} Rs {i['split'].invoice_total}: pay Rs {sp.base_payout} now, TDS Rs {sp.tds}, "
                   f"GST Rs {sp.gst_escrow} held in escrow. " + " ".join(s["alerts"]))
        self.c.call("whatsapp-voice", "send_interactive_approval_card", to=s["owner_phone"], summary=summary,
                    buttons=["Pay (split)", "Hold", "Ask CA"])
        s["status"] = "PROPOSED"
