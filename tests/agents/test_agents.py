from datetime import date, datetime
from decimal import Decimal

import pytest
from taxsetu_agents import (DirectTaxAgent, ExplainerHandoffAgent, Graph, IngestionAgent, LogisticsAgent, LoopCapExceeded,
                            ReconChaseAgent, StubLlm)
from taxsetu_api.hitl import HitlGate
from taxsetu_engine.gst import gstin_check_char
from taxsetu_mcp import ToolError, mesh

D = Decimal
TODAY = date(2026, 11, 7)


def gstin(pan="ABCDE1234F", state="27"):
    g = f"{state}{pan}1Z"
    return g + gstin_check_char(g)


GOOD, SLOW, GHOST = gstin("AAAAA1111A"), gstin("BBBBB2222B"), gstin("CCCCC3333C")
OWN = gstin("OWNER1234P")   # buyer, only used as a valid GSTIN

PROFILES = {
    GOOD: {"gstin": GOOD, "status": "ACTIVE", "filings": [(True, True)] * 6},
    SLOW: {"gstin": SLOW, "status": "ACTIVE", "filings": [(True, True)] * 4 + [(True, False), (False, False)]},
    GHOST: {"gstin": GHOST, "status": "CANCELLED", "filings": []},
}


@pytest.fixture
def env():
    gate = HitlGate(b"test-secret")
    return gate, mesh(gate.agent_tools.stage, gstn={"profiles": PROFILES})


def bill(g, no="INV/402", taxable="100000", rate="18", desc="steel fabrication", hsn="7308", day="2026-11-05"):
    return (f"supplier_gstin: {g}\ninvoice_no: {no}\ninvoice_date: {day}\nhsn: {hsn}\ndescription: {desc}\n"
            f"taxable: {taxable}\nrate: {rate}")


def cards(client, phone):
    return client.read("whatsapp-voice", f"whatsapp://thread/{phone}/history")


# ---- Agent 1 -------------------------------------------------------------------------------------------------
def test_ingestion_trusted_supplier_is_paid_in_full_upfront(env):
    _, c = env
    s = IngestionAgent(c, StubLlm()).run("T1", "91", bill(GOOD), "27")
    assert s["status"] == "PROPOSED" and s["trust_score"] == 900
    assert (s["inv"]["split"].cgst, s["inv"]["split"].sgst, s["inv"]["split"].igst) == (D("9000.00"), D("9000.00"), D("0.00"))
    assert s["split"].gst_escrow == 0 and s["split"].total == D("118000.00")
    assert cards(c, "91")[0]["buttons"] == ["Pay (split)", "Hold", "Ask CA"]


def test_ingestion_defaulter_gets_escrow_tds_and_alerts(env):
    _, c = env
    s = IngestionAgent(c, StubLlm()).run("T1", "91", bill(SLOW), "27", tds_section="194C")
    assert s["status"] == "PROPOSED" and s["trust_score"] < 800
    sp = s["split"]
    assert (sp.base_payout, sp.tds, sp.gst_escrow) == (D("98000.00"), D("2000.00"), D("18000.00"))   # report's Rs 1,18,000 example
    assert any("missed" in a for a in s["alerts"]) and any("TDS" in a for a in s["alerts"])
    assert sum(r[1] for r in s["ledger"]) == sum(r[2] for r in s["ledger"])


def test_ingestion_cancelled_supplier_and_blocked_credit_and_interstate(env):
    _, c = env
    s = IngestionAgent(c, StubLlm()).run("T1", "91", bill(GHOST, desc="restaurant catering", hsn="9963"), "29")
    assert s["trust_score"] == 0 and s["inv"]["split"].igst == D("18000.00")          # buyer in another state -> IGST
    assert any("CANCELLED" in a for a in s["alerts"]) and any("17(5)" in a for a in s["alerts"])
    assert not any("Credit Ledger" in r[0] for r in s["ledger"])                       # blocked ITC is expensed, not credited


def test_ingestion_dedups_formatting_variants_of_the_same_invoice(env):
    _, c = env
    a = IngestionAgent(c, StubLlm())
    assert a.run("T1", "91", bill(GOOD, no="INV/402"), "27")["status"] == "PROPOSED"
    assert a.run("T1", "91", bill(GOOD, no="inv-402"), "27")["status"] == "DUPLICATE"
    assert len(cards(c, "91")) == 1


@pytest.mark.parametrize("text", ["", "hello", bill(GOOD).replace(GOOD, GOOD[:-1] + "0"), bill(GOOD, taxable="abc"),
                                  bill(GOOD, rate="900"), bill(GOOD, day="07/11/2026"), bill(GOOD, taxable="-5")])
def test_ingestion_never_guesses_on_bad_extraction(env, text):
    _, c = env
    s = IngestionAgent(c, StubLlm()).run("T1", "91", text, "27")
    assert s["status"] == "NEEDS_REVIEW" and s["errors"] and cards(c, "91") == []


# ---- Agent 2 -------------------------------------------------------------------------------------------------
def _purchase(no, tax="18000", gstin_=GOOD, taxable="100000", day=date(2026, 10, 20), paid=False, phone="98"):
    return dict(gstin=gstin_, inv_no=no, taxable=taxable, tax=tax, pos="27", invoice_date=day, paid=paid, phone=phone)


def test_recon_agent_matches_chases_and_flags_rule37():
    t = [0.0]
    c = mesh(clock=lambda: t[0], gstn={"gstr2b": {(OWN, "102026"): [
        dict(gstin=GOOD, inv_no="A-1", taxable="100000", tax="18000", pos="27"),
        dict(gstin=GOOD, inv_no="B-2O", taxable="50000", tax="9000", pos="27"),       # supplier typo (O for 0)
        dict(gstin=SLOW, inv_no="C-3", taxable="10000", tax="1800", pos="27"),        # tax differs from our books
    ]}})
    purchases = [_purchase("A-1"), _purchase("B-20", "9000", taxable="50000"), _purchase("C-3", "2000", SLOW, "10000"),
                 _purchase("D-4", "500", GOOD, "2777.78", day=date(2026, 3, 1))]       # missing from 2B and 250 days old
    s = ReconChaseAgent(c).run("T1", OWN, "102026", purchases, TODAY)
    assert s["summary"]["statuses"] == ["EXACT", "FUZZY", "MISMATCH", "MISSING_2B"]
    assert s["summary"]["eligible_itc"] == D("27000.00") and s["summary"]["deferred_itc"] == D("2500.00")
    assert sorted(s["nudged"]) == ["C-3", "D-4"] and s["ca_queue"] == []
    assert [r["inv_no"] for r in s["rule37"]] == ["D-4"] and s["rule37"][0]["status"] == "REVERSE"


def test_recon_agent_loop_is_capped_at_three_nudges_then_escalates():
    t = [0.0]
    c = mesh(clock=lambda: t[0], gstn={"gstr2b": {(OWN, "102026"): []}})
    a, out = ReconChaseAgent(c), []
    for _ in range(5):                                         # the scheduler re-runs it, with and without the 48h gap
        out.append(a.run("T1", OWN, "102026", [_purchase("X-9")], TODAY))
        t[0] += 49 * 3600 if len(out) != 2 else 3600            # run #3 comes only 1h after #2
    assert [(o["nudged"], o["waiting"], o["ca_queue"]) for o in out] == [
        (["X-9"], [], []), (["X-9"], [], []), ([], ["X-9"], []), (["X-9"], [], []), ([], [], ["X-9"])]
    assert len([m for m in cards(c, "98") if m["kind"] == "nudge"]) == 3


# ---- Agent 3 -------------------------------------------------------------------------------------------------
def test_logistics_generates_stages_and_alerts_before_expiry(env):
    gate, c = env
    s = LogisticsAgent(c).run_generate("T1", "97", GOOD, "INV/7", date(2026, 11, 7), "tn 09-bc 4411", 450, "75000")
    assert s["status"] == "STAGED" and s["result"]["alert_at"] == s["result"]["valid_until"] - (s["result"]["valid_until"] - s["result"]["alert_at"])
    assert gate.agent_tools.get("T1", s["result"]["draft_id"])["status"] == "DRAFT_STAGED"
    assert cards(c, "97")[0]["buttons"] == ["Approve EWB", "Edit", "Cancel"]


def test_logistics_blocks_duplicates_bad_plates_and_below_threshold(env):
    _, c = env
    a = LogisticsAgent(c)
    kw = dict(tenant_id="T1", driver_phone="97", gstin=GOOD, invoice_date=date(2026, 11, 7), distance_km=100, consignment_value="75000")
    assert a.run_generate(invoice_no="I1", vehicle_ocr="TN09BC4411", **kw)["status"] == "STAGED"
    assert a.run_generate(invoice_no="i-1", vehicle_ocr="TN09BC4411", **kw)["status"] == "DUPLICATE"      # clerk + driver double-send
    s = a.run_generate(invoice_no="I2", vehicle_ocr="T N 0 9 ? ?", **kw)
    assert s["status"] == "NEEDS_REVIEW" and "unreadable" in s["errors"][0]
    assert a.run_generate(invoice_no="I3", vehicle_ocr="TN09BC4411", **{**kw, "consignment_value": "1000"})["status"] == "NOT_REQUIRED"
    assert a.run_generate(invoice_no="I4", vehicle_ocr="TN09BC4411", **{**kw, "gstin": GOOD[:-1] + "0"})["status"] == "NEEDS_REVIEW"


def test_mov07_defence_reduces_penalty_only_when_gate_allows(env):
    _, c = env
    a = LogisticsAgent(c)
    ok = a.run_defend("T1", "91", "VEHICLE_TYPO", True, "36000", "TN09BC4411", "TN09BC4412", "2026-11-07")
    assert ok["status"] == "REPLY_DRAFTED" and str(ok["result"]["penalty"]) == "1000" and ok["result"]["citation"] == "CBIC-64/38/2018-GST"
    evasion = a.run_defend("T1", "91", "VEHICLE_TYPO", False, "36000")                  # no invoice on file = unbilled goods
    assert evasion["status"] == "ESCALATE_CA" and evasion["result"]["citation"] is None and str(evasion["result"]["penalty"]) == "72000.00"
    far = a.run_defend("T1", "91", "VEHICLE_TYPO", True, "36000", "TN09BC4411", "KA01AA9999")
    assert far["status"] == "ESCALATE_CA"                                               # not a 1-2 char typo


def test_logistics_stops_when_rule_138e_would_block_part_a():
    t = gstin("DDDDD4444D")
    prof = {t: {"gstin": t, "status": "ACTIVE", "filings": [(True, True)] * 4 + [(True, False), (True, False)]},   # 2 missed GSTR-3B in a row
            GOOD: PROFILES[GOOD]}
    gate = HitlGate(b"x")
    c = mesh(gate.agent_tools.stage, gstn={"profiles": prof})
    kw = dict(tenant_id="T1", driver_phone="97", invoice_date=date(2026, 11, 7), distance_km=100, consignment_value="75000",
              vehicle_ocr="TN09BC4411")
    s = LogisticsAgent(c).run_generate(gstin=t, invoice_no="I1", **kw)
    assert s["status"] == "BLOCKED_138E" and "GSTR-3B" in s["errors"][0] and cards(c, "97") == []
    assert gate.audit.events("T1") == []                                          # nothing was staged
    one = {**prof, t: {**prof[t], "filings": [(True, True)] * 5 + [(True, False)]}}                 # one miss: still allowed
    assert LogisticsAgent(mesh(gate.agent_tools.stage, gstn={"profiles": one})).run_generate(gstin=t, invoice_no="I2", **kw)["status"] == "STAGED"


# ---- Agent 4 -------------------------------------------------------------------------------------------------
def test_direct_tax_stages_itr4_for_digital_business(env):
    gate, c = env
    s = DirectTaxAgent(c).run("T1", "ABCDE1234F", "2026-27", 2026, "2000000", "2000000", today=TODAY)
    assert s["status"] == "STAGED" and s["route"]["form"] == "ITR-4" and D(s["total_income"]) == D("120000")
    assert gate.agent_tools.get("T1", s["draft"]["draft_id"])["kind"] == "ITR"


def test_direct_tax_cash_breach_loses_presumption_and_stages_nothing(env):
    gate, c = env
    s = DirectTaxAgent(c).run("T1", "ABCDE1234F", "2026-27", 2026, "26000000", "24600000", today=TODAY)    # 5.38% cash
    assert s["status"] == "ESCALATE_CA" and "draft" not in s and any("BREACH" in a for a in s["alerts"])
    assert len(gate.audit.events("T1")) == 0


def test_direct_tax_drafts_condonation_for_old_unclaimed_refund():
    c = mesh(itd={("unclaimed", "ABCDE1234F"): [{"ay_start_year": 2022, "amount": "12000"}]}, gstn={})
    s = DirectTaxAgent(c).run("T1", "ABCDE1234F", "2026-27", 2026, "0", "0", today=TODAY)
    assert s["petitions"][0]["drafted"] and "119(2)(b)" in s["petitions"][0]["letter"]


def test_direct_tax_rejects_bad_pan(env):
    assert DirectTaxAgent(env[1]).run("T1", "BAD", "2026-27", 2026, "1", "1")["status"] == "NEEDS_REVIEW"


# ---- Agent 5 -------------------------------------------------------------------------------------------------
class LyingLlm(StubLlm):
    def draft(self, kind, facts):
        return "Your net cash payable is only Rs 4,500 this month."          # invented figure


def _handoff(c, llm, locale="hi"):
    from taxsetu_engine import payments
    sp = payments.split_payment(100000, 18000, 100, "194C")
    v = [dict(vendor="Ramesh <Traders>", inv_no="INV/402", date=date(2026, 11, 7), lines=payments.purchase_ledger_entries(100000, 18000, sp))]
    return ExplainerHandoffAgent(c, llm).run("T1", "91", locale, OWN, "102026", "Demo & Co", "GSTR3B",
                                             {"out": D("45000.00"), "itc": D("18000.00"), "net": D("27000.00")}, v)


def test_explainer_handoff_packets_stage_and_vernacular_voice(env):
    import xml.etree.ElementTree as ET
    gate, c = env
    s = _handoff(c, StubLlm())
    assert s["status"] == "HANDED_OFF" and not s["llm_rejected"] and "27000.00" in s["summary_text"] and "₹" in s["summary_text"]
    assert ET.fromstring(s["tally_xml"][0]).find(".//PARTYLEDGERNAME").text == "Ramesh <Traders>"
    assert gate.agent_tools.get("T1", s["draft"]["draft_id"])["kind"] == "GSTR3B"
    assert cards(c, "91")[0]["locale"] == "hi"


def test_explainer_rejects_llm_prose_with_ungrounded_numbers(env):
    _, c = env
    s = _handoff(c, LyingLlm(), "en")
    assert s["llm_rejected"] and "4,500" not in s["summary_text"] and "27000.00" in s["summary_text"]


# ---- cross-cutting -------------------------------------------------------------------------------------------
def test_graph_hard_step_cap():
    g = Graph(max_steps=5)
    g.node("a", "b")(lambda s: None)
    g.node("b", "a")(lambda s: None)
    with pytest.raises(LoopCapExceeded):
        g.run("a", {})


def test_agents_stage_but_only_a_human_otp_can_file(env):
    gate, c = env
    s = DirectTaxAgent(c).run("T1", "ABCDE1234F", "2026-27", 2026, "2000000", "2000000", today=TODAY)
    did, sha = s["draft"]["draft_id"], s["draft"]["payload_sha256"]
    for evil in ("retfile_gstr3b", "file_return", "ims_reject_invoice", "authorize_filing"):
        with pytest.raises(ToolError, match="unknown tool"):
            c.call("gstn-nic", evil)                                      # the mesh simply has no such capability
    assert gate.agent_tools.get("T1", did)["status"] == "DRAFT_STAGED"
    ack = gate.authorize("T1", did, sha, gate.request_otp("T1", did))     # the human path
    assert ack["status"] == "FILED_VERIFIED" and ack["simulated"] is True
    assert gate.audit.verify()
