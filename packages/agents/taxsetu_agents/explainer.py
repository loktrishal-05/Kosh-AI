"""Agent 5: practitioner handoff + plain-language explainer. Builds the CA's Tally packets and stages the return; the owner gets a
voice summary whose every number must match engine output. It stages, it does not file ('Approve & File' is the human API)."""
import hashlib
from datetime import date

from taxsetu_engine.tally import purchase_voucher_xml

from .graph import Graph
from .llm import grounded, template_summary


def mock_tts(text: str, locale: str) -> str:
    return f"mock://tts/{locale}/{hashlib.sha256(text.encode()).hexdigest()[:12]}.ogg"


class ExplainerHandoffAgent:
    def __init__(self, client, llm, tts=mock_tts):
        self.c, self.llm, self.tts = client, llm, tts
        g = self.g = Graph()
        g.node("packets", "stage")(self.packets)
        g.node("stage", "explain")(self.stage)
        g.node("explain")(self.explain)

    def run(self, tenant_id: str, owner_phone: str, locale: str, gstin: str, period: str, company: str, return_type: str,
            figures: dict, vouchers: list) -> dict:
        """figures: {out, itc, net} (Decimal-able, from the engine). vouchers: [{vendor, inv_no, date, lines}] ledger rows per bill."""
        return self.g.run("packets", dict(tenant_id=tenant_id, phone=owner_phone, locale=locale, gstin=gstin, period=period,
                                          company=company, rtype=return_type, figures={k: str(v) for k, v in figures.items()},
                                          vouchers=vouchers))

    def packets(self, s):    # exported for the CA dashboard; NOT posted into Tally (post_tally_voucher is a human-approved action)
        s["tally_xml"] = [purchase_voucher_xml(s["company"], v["vendor"], v["inv_no"], v["date"], v["lines"]) for v in s["vouchers"]]

    def stage(self, s):
        s["draft"] = self.c.call("gstn-nic", "stage_gstr1_or_3b_retsave", tenant_id=s["tenant_id"], gstin=s["gstin"], period=s["period"],
                                 return_type=s["rtype"], json_body={"figures": s["figures"]})

    def explain(self, s):
        facts = {**s["figures"], "locale": s["locale"]}
        text = self.llm.draft("vernacular_summary", facts)
        s["llm_rejected"] = not grounded(text, s["figures"])    # hallucinated figure -> fall back to the fixed template
        s["summary_text"] = template_summary(facts) if s["llm_rejected"] else text
        uri = self.tts(s["summary_text"], s["locale"])
        self.c.call("whatsapp-voice", "push_vernacular_voice_summary", to=s["phone"], locale=s["locale"], audio_uri=uri)
        s["status"] = "HANDED_OFF"
