import json
from decimal import Decimal
from datetime import date, datetime, timedelta

import pytest
from taxsetu_engine.gst import gstin_check_char
from taxsetu_mcp import Server, ToolError, mesh, statutory_rag as rag
from taxsetu_mcp.core import FORBIDDEN


def gstin(pan="ABCDE1234F", state="27"):
    g = f"{state}{pan}1Z"
    return g + gstin_check_char(g)


class Stager:                      # stands in for HitlGate.agent_tools.stage
    def __init__(self):
        self.calls = []

    def __call__(self, tenant, kind, payload):
        self.calls.append((tenant, kind, payload))
        return {"draft_id": f"d{len(self.calls)}", "status": "DRAFT_STAGED"}


def rpc(server, method, **params):
    return server.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def test_mesh_has_the_eight_servers_and_no_filing_tool():
    c = mesh()
    assert len(c.servers) == 8
    assert not [t for t in c.tool_names() if FORBIDDEN.search(t)]          # air-gap: nothing that files/approves/rejects/OTPs


@pytest.mark.parametrize("name", ["retfile_gstr3b", "ims_reject_invoice", "authorize_filing", "verify_otp", "file_return", "submit_return"])
def test_forbidden_tool_names_cannot_even_be_registered(name):
    s = Server("x")
    f = lambda: None
    f.__name__ = name
    with pytest.raises(ValueError):
        s.tool(f)


def test_json_rpc_roundtrip_and_error_shapes():
    s = mesh().servers["statutory-rag"]
    assert rpc(s, "initialize")["result"]["serverInfo"]["name"] == "mcp-server-statutory-rag"
    tools = rpc(s, "tools/list")["result"]["tools"]
    assert {t["name"] for t in tools} >= {"search_effective_dated_statute", "verify_citation"}
    ok = rpc(s, "tools/call", name="verify_citation", arguments={"citation_id": "CGST-r37", "on_date": "2026-01-01"})["result"]
    assert json.loads(ok["content"][0]["text"])["id"] == "CGST-r37" and "isError" not in ok
    bad = rpc(s, "tools/call", name="verify_citation", arguments={"citation_id": "MADE-UP-1", "on_date": "2026-01-01"})["result"]
    assert bad["isError"] is True
    assert rpc(s, "nope")["error"]["code"] == -32601
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_money_in_tool_results_is_an_exact_string():
    r = rpc(mesh().servers["paytm-upi-aa"], "tools/call", name="execute_split_vendor_payout",
            arguments={"inv_id": "I1", "taxable": "100000", "gst": "18000", "trust_score": 500, "tds_section": "194C"})["result"]
    sc = r["structuredContent"]
    assert (sc["base_payout"], sc["tds"], sc["gst_escrow"]) == ("98000.00", "2000.00", "18000.00")


# ---- statutory RAG -------------------------------------------------------------------------------------------
def test_effective_dating_picks_the_version_in_force():
    assert "2 crore" in rag.effective("ITA-s44AD", date(2022, 6, 1))["text"]
    assert "3 crore" in rag.effective("ITA-s44AD", date(2024, 6, 1))["text"]
    with pytest.raises(ToolError):
        rag.effective("CBIC-64/38/2018-GST", date(2018, 1, 1))              # not yet issued
    with pytest.raises(ToolError):
        rag.effective("CBIC-999/99/2099-GST", date(2026, 1, 1))             # hallucinated circular


def test_search_finds_the_circular_and_respects_domain():
    hits = rag.search("e-way bill vehicle number clerical error penalty", date(2026, 1, 1))
    assert hits[0]["id"] == "CBIC-64/38/2018-GST"
    assert all(h["domain"] == "incometax" for h in rag.search("presumptive turnover limit", date(2026, 1, 1), "incometax"))
    assert rag.search("zzzz qqqq", date(2026, 1, 1)) == []


def test_hsn_rate_never_guessed():
    s = mesh().servers["statutory-rag"]
    assert s.call("verify_hsn_sac_tax_rate", {"hsn": "0713", "on_date": "2026-01-01"})["status"] == "NOT_FOUND"
    s2 = rag.build({"07": [(date(2020, 1, 1), date(9999, 12, 31), 5)]})
    assert s2.call("verify_hsn_sac_tax_rate", {"hsn": "0713", "on_date": "2026-01-01"})["rate_pct"] == 5


def test_resource_uri_templates():
    s = mesh().servers["statutory-rag"]
    assert s.read("law://cgst/section/17(5)?date=2026-01-01")["id"] == "CGST-s17(5)"
    assert "3 crore" in s.read("law://incometax/section/44AD?date=2025-01-01")["text"]
    assert s.read("law://cbic/circulars/64%2F38%2F2018-GST?date=2026-01-01")["id"] == "CBIC-64/38/2018-GST"


# ---- gstn-nic ------------------------------------------------------------------------------------------------
def test_gstn_stage_tools_only_stage_and_validate():
    st = Stager()
    c = mesh(st)
    g = gstin()
    c.call("gstn-nic", "stage_gstr1_or_3b_retsave", tenant_id="T1", gstin=g, period="112026", return_type="GSTR3B", json_body={"x": 1})
    assert st.calls == [("T1", "GSTR3B", {"gstin": g, "period": "112026", "x": 1})]
    with pytest.raises(ToolError):
        c.call("gstn-nic", "stage_gstr1_or_3b_retsave", tenant_id="T1", gstin=g, period="p", return_type="GSTR9", json_body={})
    with pytest.raises(ToolError, match="no staging gateway"):
        mesh().call("gstn-nic", "stage_gstr1_or_3b_retsave", tenant_id="T", gstin=g, period="p", return_type="GSTR1", json_body={})


def test_ewb_generation_and_extension_window():
    st = Stager()
    c = mesh(st)
    g = gstin()
    r = c.call("gstn-nic", "generate_eway_bill_v103", tenant_id="T1", gstin=g, vehicle_no="TN09BC4411", distance_km=450,
               consignment_value="75000")
    assert r["required"] and r["alert_at"] == r["valid_until"] - timedelta(hours=4)
    assert c.call("gstn-nic", "generate_eway_bill_v103", tenant_id="T1", gstin=g, vehicle_no="X", distance_km=10,
                  consignment_value="1000")["required"] is False
    exp = datetime(2026, 11, 8, 0, 0)
    ok = c.call("gstn-nic", "extend_or_update_ewb_part_b", tenant_id="T1", gstin=g, ewb_no="1", vehicle_no="TN09BC4412",
                valid_until=exp.isoformat(), reason="BREAKDOWN", now=(exp - timedelta(hours=4)).isoformat())
    assert ok["status"] == "DRAFT_STAGED"
    with pytest.raises(ToolError):
        c.call("gstn-nic", "extend_or_update_ewb_part_b", tenant_id="T1", gstin=g, ewb_no="1", vehicle_no="V",
               valid_until=exp.isoformat(), reason="late", now=(exp + timedelta(hours=9)).isoformat())


def test_mov07_reply_cites_only_when_gate_allows():
    c = mesh()
    yes = c.call("gstn-nic", "draft_mov07_circular_64_38_reply", defect="VEHICLE_TYPO", valid_invoice_on_file=True,
                 tax_payable="36000", declared_vehicle="TN09BC4411", actual_vehicle="TN09BC4412", on_date="2026-11-07")
    assert yes["circular_applies"] and yes["citation"] == "CBIC-64/38/2018-GST" and str(yes["penalty"]) == "1000"
    no = c.call("gstn-nic", "draft_mov07_circular_64_38_reply", defect="VEHICLE_TYPO", valid_invoice_on_file=False, tax_payable="36000")
    assert not no["circular_applies"] and no["citation"] is None and "Escalate to CA" in no["letter"]


# ---- tally / whatsapp / payments / itd / workspace -----------------------------------------------------------
def test_tally_refuses_unbalanced_or_malformed_xml():
    from taxsetu_engine import payments
    from taxsetu_engine.tally import purchase_voucher_xml
    c = mesh()
    sp = payments.split_payment(100000, 18000, 100, "194C")
    xml = purchase_voucher_xml("Co", "V", "INV/1", date(2026, 11, 7), payments.purchase_ledger_entries(100000, 18000, sp))
    assert c.call("tally-xml", "post_tally_voucher", voucher_type="Purchase", xml_payload=xml)["posted"]
    assert c.read("tally-xml", "tally://company/active/daybook/2026-11-07")[0]["no"] == "INV/1"
    with pytest.raises(ToolError, match="balance"):
        c.call("tally-xml", "post_tally_voucher", voucher_type="Purchase", xml_payload=xml.replace("<AMOUNT>-", "<AMOUNT>-9", 1))
    with pytest.raises(ToolError, match="malformed"):
        c.call("tally-xml", "post_tally_voucher", voucher_type="Purchase", xml_payload="<ENVELOPE>")


def test_party_ledger_is_idempotent_and_validates_gstin():
    c = mesh()
    g = gstin()
    assert c.call("tally-xml", "create_party_ledger", gstin=g, name="Ramesh & Co", state="Maharashtra")["created"]
    assert not c.call("tally-xml", "create_party_ledger", gstin=g, name="Ramesh & Co", state="Maharashtra")["created"]
    bad = g[:-1] + ("0" if g[-1] != "0" else "1")
    with pytest.raises(ToolError):
        c.call("tally-xml", "create_party_ledger", gstin=bad, name="x", state="y")


def test_whatsapp_nudge_cap_is_enforced_in_the_tool():
    t = [0.0]
    c = mesh(clock=lambda: t[0])

    def send():
        return c.call("whatsapp-voice", "dispatch_supplier_2b_nudge", supplier_phone="9", inv_no="402", bill_img_uri="u", period="112026")

    assert send()["nudge_no"] == 1
    assert send()["verdict"] == "WAIT"                       # inside 48h cooldown
    for n in (2, 3):
        t[0] += 49 * 3600
        assert send()["nudge_no"] == n
    t[0] += 49 * 3600
    assert send() == {"sent": False, "verdict": "ESCALATE_CA"}   # 4th nudge refused, goes to the CA queue
    assert len(c.read("whatsapp-voice", "whatsapp://thread/9/history")) == 3


def test_whatsapp_card_button_limit_and_locale():
    c = mesh()
    with pytest.raises(ToolError):
        c.call("whatsapp-voice", "send_interactive_approval_card", to="9", summary="s", buttons=["a", "b", "c", "d"])
    with pytest.raises(ToolError):
        c.call("whatsapp-voice", "push_vernacular_voice_summary", to="9", locale="fr", audio_uri="u")


def test_escrow_is_held_then_terminal():
    c = mesh()
    r = c.call("paytm-upi-aa", "execute_split_vendor_payout", inv_id="402", taxable="100000", gst="18000", trust_score=100)
    assert r["status"].startswith("INTENT_CREATED") and r["escrow_id"] in c.read("paytm-upi-aa", "escrow://gst-holds/active")
    assert c.call("paytm-upi-aa", "release_or_refund_gst_escrow", escrow_id=r["escrow_id"], gstr2b_matched=True)["state"] == "RELEASED"
    with pytest.raises(ToolError, match="already"):
        c.call("paytm-upi-aa", "release_or_refund_gst_escrow", escrow_id=r["escrow_id"], gstr2b_matched=False)
    trusted = c.call("paytm-upi-aa", "execute_split_vendor_payout", inv_id="9", taxable="100000", gst="18000", trust_score=850)
    assert trusted["escrow_id"] is None


def test_itd_tools_use_the_engine():
    st = Stager()
    c = mesh(st)
    r = c.call("incometax-traces", "compute_presumptive_44ad_44ada_44ae", gst_sales="1000000", bank_credits="1000000")
    assert r["eligible"] and Decimal(r["income"]) == 60000          # all-digital 6%
    assert c.call("incometax-traces", "evaluate_itr_eligibility_1_to_7",
                  profile_json={"entity": "INDIVIDUAL", "total_income": "600000", "business_income": True, "presumptive": True})["form"] == "ITR-4"
    c.call("incometax-traces", "validate_and_stage_itr_json", tenant_id="T", ay="2026-27", itr_form="ITR-4", payload={"pan": "ABCDE1234F"})
    assert st.calls[0][1] == "ITR"
    with pytest.raises(ToolError):
        c.call("incometax-traces", "validate_and_stage_itr_json", tenant_id="T", ay="2026-27", itr_form="ITR-4", payload={"pan": "BAD"})


def test_condonation_petition_only_in_the_119_2b_window():
    c = mesh()
    late = c.call("incometax-traces", "generate_sec_119_2b_condonation_petition", pan="ABCDE1234F", ay_start_year=2022,
                  refund_amt="12000", reason="TDS credit discovered late", today="2026-11-07")
    assert late["drafted"] and late["citation"] == "ITA-s119(2)(b)"
    inwin = c.call("incometax-traces", "generate_sec_119_2b_condonation_petition", pan="ABCDE1234F", ay_start_year=2026,
                   refund_amt="1", reason="r", today="2026-11-07")
    assert inwin["drafted"] is False and inwin["pathway"] == "SEC_139_4"


def test_phase5_generators_refuse_instead_of_faking():
    with pytest.raises(ToolError, match="Phase 5"):
        mesh().call("mca-labour", "draft_eaoa_inc34_with_entrenchment")


def test_workspace_archive_only_signed_and_calendar_idempotent():
    c = mesh()
    d = [{"date": "2026-11-11", "title": "GSTR-1"}]
    assert c.call("gworkspace-sync", "sync_compliance_schedule_to_calendar", tenant_id="T", deadlines_list=d)["added"] == 1
    assert c.call("gworkspace-sync", "sync_compliance_schedule_to_calendar", tenant_id="T", deadlines_list=d)["added"] == 0
    with pytest.raises(ToolError):
        c.call("gworkspace-sync", "archive_signed_returns_to_drive", fy="2026-27", month="11", files_list=[{"name": "draft.json"}])
    assert c.call("gworkspace-sync", "archive_signed_returns_to_drive", fy="2026-27", month="11",
                  files_list=[{"name": "r.json", "ack_no": "SIM-1"}])["archived"] == 1


def test_labour_registers_tool_masks_pii_and_reports_orphans():
    import json as _json
    emp = dict(employee_code="E1", full_name="Asha", gender="F", category="Skilled", mobile="9876543210", uan="100200300400",
               date_of_joining="2024-04-01", bank_account="123456789012", ifsc="HDFC0001234")
    wage = dict(employee_code="E1", minimum_wage_basic="9000", minimum_wage_da="1000", working_days_in_month=26, days_worked=26,
                basic_earned="10000", da="2000", hra="1000", deductions={"epf": "1440", "tds": "500"})
    orphan = {**wage, "employee_code": "E9"}
    r = mesh().call("mca-labour", "compile_labour_registers_form_a_and_b", lin="LIN-1", month="2026-10",
                    payroll_data={"employees": [emp], "wages": [wage, orphan]}, today="2026-11-07")
    assert "123456789012" not in _json.dumps(r["form_a"], default=str) and r["form_a"][0]["Bank Account Number"] == "XXXXXXXX9012"
    row = r["form_b"][0]
    assert (str(row["gross"]), str(row["net"]), str(row["employer_pf"]), row["below_minimum_wage"]) == ("13000.00", "11060.00", "1440.00", False)
    assert "missing from Form A" in r["errors"]["E9"][0]
    with pytest.raises(ToolError, match="bad payroll_data"):
        mesh().call("mca-labour", "compile_labour_registers_form_a_and_b", lin="L", month="m", payroll_data={"employees": [{"nope": 1}]})
