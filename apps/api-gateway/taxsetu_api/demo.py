"""Self-contained sandbox storyline: runs the REAL agents, MCP mesh, HITL gate and mock portal in one request on fake data.
Fresh in-memory objects per call -> stateless (serverless-safe), no auth, nothing persists, nothing real is touched."""
from datetime import date, datetime
from decimal import Decimal as D

from taxsetu_agents import (DirectTaxAgent, ExplainerHandoffAgent, IngestionAgent, LogisticsAgent, ReconChaseAgent, StubLlm)
from taxsetu_engine import payments
from taxsetu_engine.gst import gstin_check_char
from taxsetu_mcp import mesh

from .hitl import HitlGate
from .portal import PortalError

TODAY = date(2026, 11, 7)
TENANT, OWNER_PHONE, PAN = "demo-tenant", "919800000001", "ABCDE1234F"


def _gstin(pan: str, state: str = "27") -> str:
    g = f"{state}{pan}1Z"
    return g + gstin_check_char(g)


BUYER, STEEL, AGENCY = _gstin("OWNER1234P"), _gstin("BBBBB2222B"), _gstin("AAAAA1111A")


def storyline() -> dict:
    gate = HitlGate(b"sandbox-ephemeral-secret")
    c = mesh(gate.agent_tools.stage, gstn={
        "profiles": {STEEL: {"gstin": STEEL, "status": "ACTIVE", "filings": [(True, True)] * 4 + [(True, False), (False, False)]},
                     AGENCY: {"gstin": AGENCY, "status": "ACTIVE", "filings": [(True, True)] * 6}},
        "gstr2b": {(BUYER, "102026"): [
            dict(gstin=AGENCY, inv_no="A-1", taxable="100000", tax="18000", pos="27"),
            dict(gstin=AGENCY, inv_no="B-2O", taxable="50000", tax="9000", pos="27"),
            dict(gstin=STEEL, inv_no="C-3", taxable="10000", tax="1800", pos="27")]}})
    steps = []

    def add(agent, title, facts, note=""):
        steps.append({"n": len(steps) + 1, "agent": agent, "title": title, "facts": [[k, str(v)] for k, v in facts], "note": note})

    # 1. WhatsApp bill -> proposal
    bill = (f"supplier_gstin: {STEEL}\ninvoice_no: INV/402\ninvoice_date: 2026-11-05\nhsn: 7308\n"
            "description: steel fabrication\ntaxable: 100000\nrate: 18")
    s = IngestionAgent(c, StubLlm()).run(TENANT, OWNER_PHONE, bill, "27", tds_section="194C")
    sp = s["split"]
    add("Agent 1 - Ingestion", "Bill photo forwarded on WhatsApp", [
        ("Supplier trust score", f"{s['trust_score']} / 900"), ("GST split", f"CGST {s['inv']['split'].cgst} + SGST {s['inv']['split'].sgst}"),
        ("Pay now (net base)", f"Rs {sp.base_payout}"), ("TDS u/s 194C withheld", f"Rs {sp.tds}"),
        ("GST held in escrow", f"Rs {sp.gst_escrow}"), ("Alerts", " | ".join(s["alerts"]))],
        "Supplier missed recent filings, so GST is parked until the invoice appears in GSTR-2B. Owner gets a one-tap card.")

    # 2. 2B reconciliation + chasing
    def pur(no, tax, g, taxable, day=date(2026, 10, 20)):
        return dict(gstin=g, inv_no=no, taxable=taxable, tax=tax, pos="27", invoice_date=day, paid=False, phone="919800000099")
    r = ReconChaseAgent(c).run(TENANT, BUYER, "102026", [pur("A-1", "18000", AGENCY, "100000"), pur("B-20", "9000", AGENCY, "50000"),
                                                       pur("C-3", "2000", STEEL, "10000"),
                                                       pur("D-4", "500", AGENCY, "2777.78", date(2026, 3, 1))], TODAY)
    add("Agent 2 - Recon & chase", "14th-of-month GSTR-2B reconciliation", [
        ("Statuses", ", ".join(r["summary"]["statuses"])), ("ITC safe to claim", f"Rs {r['summary']['eligible_itc']}"),
        ("ITC deferred", f"Rs {r['summary']['deferred_itc']}"), ("Suppliers nudged on WhatsApp", ", ".join(r["nudged"])),
        ("Rule 37 (180-day) alert", ", ".join(f"{x['inv_no']}: {x['status']}" for x in r["rule37"]))],
        "Typo'd invoice number matched by fuzzy tier. Nudges are capped at 3 per invoice with a 48h cooldown, then escalate to the CA.")

    # 3. Checkpoint defence + EWB
    lg = LogisticsAgent(c)
    m = lg.run_defend(TENANT, OWNER_PHONE, "VEHICLE_TYPO", True, "36000", "TN09BC4411", "TN09BC4412", TODAY.isoformat())
    bad = lg.run_defend(TENANT, OWNER_PHONE, "VEHICLE_TYPO", False, "36000")
    e = lg.run_generate(TENANT, OWNER_PHONE, AGENCY, "INV/7", TODAY, "TN 09 BC 4411", 450, "75000")
    add("Agent 3 - Logistics", "Roving-squad detention notice (MOV-07)", [
        ("1-digit plate typo, invoice on file", f"penalty Rs {m['result']['penalty']} (cites {m['result']['citation']})"),
        ("Same notice, NO invoice on file", f"exposure Rs {bad['result']['penalty']}, no circular cited, escalate to CA"),
        ("e-Way Bill (450 km)", f"valid until {e['result']['valid_until']:%d %b %H:%M}, expiry alert at {e['result']['alert_at']:%d %b %H:%M}")],
        "Relief is unlocked only by the deterministic gate; the citation must also resolve in the statutory corpus.")

    # 4. ITR
    t = DirectTaxAgent(c).run(TENANT, PAN, "2026-27", 2026, "2000000", "2000000", today=TODAY)
    add("Agent 4 - Direct tax", "Presumptive income and ITR routing", [
        ("Form", t["route"]["form"]), ("Presumptive income (44AD, all digital)", f"Rs {D(t['total_income']):.2f}"),
        ("Best regime", t["regimes"]["best"]), ("Draft status", "STAGED (RETSAVE-equivalent), not filed")])

    # 5. Hand-off
    sp2 = payments.split_payment(100000, 18000, 100, "194C")
    h = ExplainerHandoffAgent(c, StubLlm()).run(
        TENANT, OWNER_PHONE, "hi", BUYER, "102026", "Demo Traders", "GSTR3B", {"out": D("45000.00"), "itc": D("27000.00"), "net": D("18000.00")},
        [dict(vendor="Steel Works", inv_no="INV/402", date=TODAY, lines=payments.purchase_ledger_entries(100000, 18000, sp2))])
    add("Agent 5 - Hand-off", "CA packet + vernacular voice summary", [
        ("Hindi voice script", h["summary_text"]), ("Tally XML vouchers exported", len(h["tally_xml"])),
        ("Return draft", f"GSTR-3B staged ({h['draft']['payload_sha256'][:12]}...)"), ("LLM figures rejected", h["llm_rejected"])],
        "Every number in the spoken summary must equal engine output, otherwise a fixed template is used.")

    # 6. Human gate
    did, sha = h["draft"]["draft_id"], h["draft"]["payload_sha256"]
    try:
        gate.authorize(TENANT, did, sha, "000000")
        wrong = "ACCEPTED (bug)"
    except PortalError as ex:
        wrong = f"REFUSED: {ex}"
    ack = gate.authorize(TENANT, did, sha, gate.request_otp(TENANT, did))
    ev = gate.audit.events(TENANT)
    add("Human gate", "Owner taps Approve & File", [
        ("Wrong OTP", wrong), ("Correct single-use OTP bound to payload hash", f"FILED_VERIFIED, ack {ack['ack_no']} (simulated)"),
        ("Audit trail", " > ".join(x["action"] for x in ev)), ("Hash chain intact", gate.audit.verify())],
        "Agents can only stage. Filing needs the owner's OTP and the exact payload hash; the portal re-checks an HMAC approval token.")
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "simulated": True, "steps": steps}
