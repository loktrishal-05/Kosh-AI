"""Agent 4: presumptive income, cash-ceiling guardrail, ITR form routing, staged ITR draft, unclaimed-refund diagnostics."""
from datetime import date

from taxsetu_engine import gst, itr, refund
from taxsetu_engine.money import d

from .graph import Graph


class DirectTaxAgent:
    def __init__(self, client):
        self.c = client
        g = self.g = Graph()
        g.node("presume", "route")(self.presume)
        g.node("route", lambda s: "stage" if s["eligible"] else "refunds")(self.route)
        g.node("stage", "refunds")(self.stage)
        g.node("refunds")(self.refunds)

    def run(self, tenant_id: str, pan: str, ay: str, ay_start_year: int, gst_sales: str, bank_credits: str,
            other_income: str = "0", today: date | None = None, entity: str = "INDIVIDUAL") -> dict:
        s = dict(tenant_id=tenant_id, pan=pan, ay=ay, ay_start_year=ay_start_year, gst_sales=gst_sales, bank_credits=bank_credits,
                 other_income=d(other_income), today=today or date.today(), entity=entity, alerts=[], petitions=[], eligible=False)
        if not gst.is_valid_pan(pan):
            return {**s, "status": "NEEDS_REVIEW", "errors": ["PAN invalid"], "trail": []}
        return self.g.run("presume" if d(gst_sales) > 0 else "refunds", s)    # no business turnover: nothing to stage, refund checks only

    def presume(self, s):
        s["pres"] = self.c.call("incometax-traces", "compute_presumptive_44ad_44ada_44ae", gst_sales=s["gst_sales"],
                                bank_credits=s["bank_credits"])
        if s["pres"]["cash_alert"] != "OK":
            s["alerts"].append(f"Cash ceiling {s['pres']['cash_alert']}: collect remaining receipts digitally")

    def route(self, s):
        p = s["pres"]
        s["total_income"] = (d(p["income"]) if p["eligible"] else d(0)) + s["other_income"]
        s["route"] = self.c.call("incometax-traces", "evaluate_itr_eligibility_1_to_7", profile_json=dict(
            entity=s["entity"], total_income=s["total_income"], business_income=True, presumptive=p["eligible"]))
        s["eligible"] = p["eligible"]
        if not p["eligible"]:
            s["status"] = "ESCALATE_CA"
            s["alerts"].append("Presumptive scheme not available (cash ceiling / limit): full books and tax audit analysis needed")

    def stage(self, s):
        reg = itr.compare_regimes(s["total_income"], salaried=False)
        s["regimes"] = reg
        s["draft"] = self.c.call("incometax-traces", "validate_and_stage_itr_json", tenant_id=s["tenant_id"], ay=s["ay"],
                                 itr_form=s["route"]["form"], payload={"pan": s["pan"], "total_income": str(s["total_income"]),
                                                                       "regime": reg["best"]})
        s["status"] = "STAGED"

    def refunds(self, s):
        for r in self.c.read("incometax-traces", f"itd://pan/{s['pan']}/5yr-unclaimed-refunds"):
            out = self.c.call("incometax-traces", "generate_sec_119_2b_condonation_petition", pan=s["pan"],
                              ay_start_year=r["ay_start_year"], refund_amt=r["amount"], reason=r.get("reason", "credit found late"),
                              today=s["today"].isoformat())
            s["petitions"].append(out)
        s.setdefault("status", "STAGED" if s.get("draft") else "NO_ACTION")
