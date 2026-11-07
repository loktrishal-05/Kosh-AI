"""mcp-server-incometax-traces (Mock sandbox). Computation is delegated to the deterministic engine; ITR JSON is staged, never filed."""
from datetime import date
from decimal import Decimal

from taxsetu_engine import gst, itr, refund
from taxsetu_engine.money import d

from . import statutory_rag as rag
from .core import Server, ToolError

_MONEY_FIELDS = ("total_income", "stcg_111a", "other_capital_gains", "ltcg_112a", "agri_income")


def build(stage=None, data: dict | None = None) -> Server:
    s, data = Server("mcp-server-incometax-traces"), data or {}

    @s.tool
    def evaluate_itr_eligibility_1_to_7(profile_json: dict) -> dict:
        """Route to ITR-1..7 from a Taxpayer profile (field names as in taxsetu_engine.itr.Taxpayer)."""
        form, why = itr.route_itr(itr.Taxpayer(**{k: d(v) if k in _MONEY_FIELDS else v for k, v in profile_json.items()}))
        return {"form": form, "reasons": why}

    @s.tool
    def compute_presumptive_44ad_44ada_44ae(gst_sales: str, bank_credits: str) -> dict:
        """Digital = bank credits (capped at GST sales); the rest is treated as cash. Returns 44AD result + cash-ceiling alert."""
        total = d(gst_sales)
        digital = min(d(bank_credits), total)
        r = itr.presumptive_44ad(digital, total - digital)
        return {"eligible": r.eligible, "income": r.income, "cash_alert": itr.cash_ceiling_alert(digital, total - digital)}

    @s.tool(hitl=True)
    def validate_and_stage_itr_json(tenant_id: str, ay: str, itr_form: str, payload: dict) -> dict:
        """Stage an ITR draft (RETSAVE-equivalent). Filing requires the human EVC/OTP step in the API."""
        if stage is None:
            raise ToolError("no staging gateway configured")
        if not gst.is_valid_pan(payload.get("pan", "")):
            raise ToolError("invalid PAN")
        return stage(tenant_id, "ITR", {**payload, "assessment_year": ay, "form": itr_form})

    @s.tool(hitl=True)
    def generate_sec_119_2b_condonation_petition(pan: str, ay_start_year: int, refund_amt: str, reason: str, today: str = "") -> dict:
        """Petition draft only when the deterministic pathway is SEC_119_2B; otherwise tells the caller the right route."""
        on = date.fromisoformat(today) if today else date.today()
        adv = refund.pick_refund_pathway(ay_start_year, on)
        if adv.pathway != "SEC_119_2B":
            return {"drafted": False, "pathway": adv.pathway, "notes": adv.notes}
        cite = rag.effective("ITA-s119(2)(b)", on)["id"]
        return {"drafted": True, "pathway": adv.pathway, "citation": cite, "deadline": adv.deadline,
                "letter": f"PAN {pan}, AY {ay_start_year}-{str(ay_start_year + 1)[2:]}: request condonation of delay under {cite} to "
                          f"claim refund of Rs {Decimal(refund_amt):,.2f}. Genuine hardship: {reason}"}

    for tmpl, key in (("itd://pan/{pan}/ais-tis/{ay}", "ais"), ("itd://pan/{pan}/form26as/{ay}", "26as"),
                      ("traces://tan/{pan}/form16-part-a/{ay}", "form16a")):
        s.resource(tmpl)(lambda pan, ay, key=key: data.get((key, pan, ay), []))
    s.resource("itd://pan/{pan}/5yr-unclaimed-refunds")(lambda pan: data.get(("unclaimed", pan), []))
    return s
