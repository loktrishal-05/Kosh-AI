"""Agent 2: GSTR-2B reconciliation + supplier chasing. One nudge attempt per invoice per run; the 3-nudge/48h cap lives in the
WhatsApp tool (and the engine) so a re-running or looping agent still cannot spam. Exhausted items go to the CA exception queue."""
from datetime import date

from taxsetu_engine import gst, recon
from taxsetu_engine.money import d

from .graph import Graph


def _inv(r: dict) -> recon.Inv:
    return recon.Inv(r["gstin"], r["inv_no"], d(r["taxable"]), d(r["tax"]), r.get("pos", ""))


class ReconChaseAgent:
    def __init__(self, client):
        self.c = client
        g = self.g = Graph()
        g.node("pull_2b", "reconcile")(lambda s: s.update(b=self.c.read("gstn-nic", f"gst://returns/{s['gstin']}/{s['period']}/gstr2b")))
        g.node("reconcile", "rule37")(self.reconcile)
        g.node("rule37", "chase")(self.rule37)
        g.node("chase")(self.chase)

    def run(self, tenant_id: str, gstin: str, period: str, purchases: list, today: date) -> dict:
        """purchases: [{gstin, inv_no, taxable, tax, pos, invoice_date: date, paid: bool, phone, img}]"""
        return self.g.run("pull_2b", dict(tenant_id=tenant_id, gstin=gstin, period=period, purchases=purchases, today=today,
                                          nudged=[], waiting=[], ca_queue=[], rule37=[]))

    def reconcile(self, s):
        s["recon"] = recon.reconcile([_inv(p) for p in s["purchases"]], [_inv(r) for r in s["b"]])
        s["by_key"] = {(p["gstin"], p["inv_no"]): p for p in s["purchases"]}

    def rule37(self, s):
        for p in s["purchases"]:
            r = gst.rule37_status(p["invoice_date"], s["today"], p["paid"], p["tax"])
            if r["status"] != "OK" and r["status"] != "SETTLED":
                s["rule37"].append({"inv_no": p["inv_no"], **r})

    def chase(self, s):
        for inv in s["recon"]["chase"]:
            p = s["by_key"][(inv.gstin, inv.inv_no)]
            res = self.c.call("whatsapp-voice", "dispatch_supplier_2b_nudge", supplier_phone=p["phone"], inv_no=p["inv_no"],
                              bill_img_uri=p.get("img", ""), period=s["period"])
            {"SEND": s["nudged"], "WAIT": s["waiting"], "ESCALATE_CA": s["ca_queue"]}[res["verdict"]].append(p["inv_no"])
        s["summary"] = {"eligible_itc": s["recon"]["eligible_itc"], "deferred_itc": s["recon"]["deferred_itc"],
                        "statuses": [r["status"] for r in s["recon"]["rows"]]}
