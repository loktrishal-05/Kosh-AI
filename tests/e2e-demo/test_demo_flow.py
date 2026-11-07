"""End-to-end: the report's 5-minute demo storyline through the real HTTP API (mock portal)."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from taxsetu_api import auth
from taxsetu_api.main import create_app
from taxsetu_engine import gst

SECRET, WA = b"s3cret", b"wa-secret"
G1 = "29ABCDE1234F1Z" + gst.gstin_check_char("29ABCDE1234F1Z")
G2 = "33AAACT2727Q1Z" + gst.gstin_check_char("33AAACT2727Q1Z")


@pytest.fixture
def client():
    return TestClient(create_app(SECRET, WA))


def hdr(role="OWNER", tenant="T1"):
    return {"Authorization": "Bearer " + auth.encode({"role": role, "tenant_id": tenant}, SECRET)}


def test_auth_required_and_roles_enforced(client):
    assert client.get("/api/v1/audit").status_code == 401
    assert client.get("/api/v1/audit", headers={"Authorization": "Bearer junk"}).status_code == 401
    expired = auth.encode({"role": "OWNER", "tenant_id": "T1"}, SECRET, ttl_s=-10)
    assert client.get("/api/v1/audit", headers={"Authorization": "Bearer " + expired}).status_code == 401
    forged = auth.encode({"role": "OWNER", "tenant_id": "T1"}, b"other-key")
    assert client.get("/api/v1/audit", headers={"Authorization": "Bearer " + forged}).status_code == 401
    assert client.get("/api/v1/audit", headers=hdr("DRIVER")).status_code == 403


def test_whatsapp_webhook_hmac_and_idempotency(client):
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [{"id": "wamid.1"}, {"id": "wamid.2"}]}}]}]}).encode()
    sig = "sha256=" + hmac.new(WA, body, hashlib.sha256).hexdigest()
    h = {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}
    assert client.post("/api/v1/webhooks/whatsapp", content=body, headers={**h, "X-Hub-Signature-256": "sha256=bad"}).status_code == 401
    assert client.post("/api/v1/webhooks/whatsapp", content=body).status_code == 401
    assert client.post("/api/v1/webhooks/whatsapp", content=body, headers=h).json()["new_messages"] == 2
    assert client.post("/api/v1/webhooks/whatsapp", content=body, headers=h).json()["new_messages"] == 0   # replay


def test_demo_gstr2b_recon_and_chase(client):
    inv = lambda g, n, tax: {"gstin": g, "inv_no": n, "taxable": "1000", "tax": str(tax)}
    r = client.post(f"/api/v1/gst/{G1}/reconcile-2b", headers=hdr(), json={
        "return_period": "102026",
        "purchases": [inv(G2, "INV-1", 180), inv(G2, "INV-2", 9000), inv(G2, "INV-3", 9000)],
        "gstr2b": [inv(G2, "INV1", 180)]}).json()
    assert [x["status"] for x in r["rows"]] == ["EXACT", "MISSING_2B", "MISSING_2B"]
    assert r["eligible_itc"] == "180.00" and r["deferred_itc"] == "18000.00" and r["to_chase"] == ["INV-2", "INV-3"]
    assert client.post("/api/v1/gst/27AAPFU0939F1ZX/reconcile-2b", headers=hdr(), json={
        "return_period": "1", "purchases": [], "gstr2b": []}).status_code == 422


def test_demo_mov07_72k_to_1k(client):
    body = {"mode": "DEFEND_MOV07", "gstin": G1, "vehicle_no": "TN01AB1234", "defect": "VEHICLE_TYPO",
            "declared_vehicle": "TN01AB1234", "actual_vehicle": "TN01AB1243", "valid_invoice_on_file": True, "tax_payable": "36000"}
    r = client.post("/api/v1/ewb/generate-or-defend", headers=hdr("DRIVER"), json=body).json()
    assert r["circular_64_38_applies"] and r["penalty"] == "1000" and "64/38/2018-GST" in r["draft_reply"]
    r = client.post("/api/v1/ewb/generate-or-defend", headers=hdr("DRIVER"), json={**body, "valid_invoice_on_file": False}).json()
    assert not r["circular_64_38_applies"] and r["penalty"] == "72000.00" and "NOT cited" in r["draft_reply"]


def test_ewb_generation_is_staged_not_filed(client):
    r = client.post("/api/v1/ewb/generate-or-defend", headers=hdr("CLERK"), json={
        "mode": "GENERATE_EWB", "gstin": G1, "vehicle_no": "TN01AB1234", "consignment_value": "118000", "distance_km": "250"}).json()
    assert r["required"] and r["status"] == "DRAFT_STAGED"
    assert not client.post("/api/v1/ewb/generate-or-defend", headers=hdr("CLERK"), json={
        "mode": "GENERATE_EWB", "gstin": G1, "vehicle_no": "X", "consignment_value": "40000"}).json()["required"]


def test_demo_itr4_stage_then_human_otp_files_on_mock_portal(client):
    pan = "ABCDE1234F"
    r = client.post(f"/api/v1/itr/{pan}/compute-and-stage", headers=hdr(), json={
        "digital_turnover": "14400000", "cash_turnover": "600000"}).json()
    assert r["form"] == "ITR-4" and r["presumptive"]["income"] == "912000" and r["regimes"]["new_tax"] == "0"
    did, sha = r["draft_id"], r["payload_sha256"]

    # a CA, a clerk, or a wrong tenant cannot sign for the owner
    body = lambda otp: {"draft_id": did, "payload_sha256": sha, "otp_or_signature": otp}
    assert client.post("/api/v1/hitl/authorize-filing", headers=hdr("CA"), json=body("1")).status_code == 403
    assert client.post("/api/v1/hitl/authorize-filing", headers=hdr("CLERK"), json=body("1")).status_code == 403
    assert client.post(f"/api/v1/hitl/request-otp/{did}", headers=hdr("OWNER", "T2")).status_code == 404

    assert client.post("/api/v1/hitl/authorize-filing", headers=hdr(), json=body("123456")).status_code == 409  # no OTP issued
    otp = client.post(f"/api/v1/hitl/request-otp/{did}", headers=hdr()).json()["mock_otp"]
    ok = client.post("/api/v1/hitl/authorize-filing", headers=hdr(), json=body(otp)).json()
    assert ok["status"] == "FILED_VERIFIED" and ok["ack_type"] == "ITR-V" and ok["simulated"] is True

    log = client.get("/api/v1/audit", headers=hdr()).json()
    assert log["valid"] and [e["action"] for e in log["events"]] == ["RETSAVE", "FILING_REJECTED", "OTP_ISSUED", "RETFILE_HITL"]   # the no-OTP attempt is audited
    assert client.get("/api/v1/audit", headers=hdr("OWNER", "T2")).json()["events"] == []     # tenant-scoped


def test_itr_q7_stcg_flips_to_itr3_and_cash_breach_blocks_presumptive(client):
    r = client.post("/api/v1/itr/ABCDE1234F/compute-and-stage", headers=hdr(), json={
        "digital_turnover": "18000000", "stcg_111a": "15000"}).json()
    assert r["form"] == "ITR-3"
    r = client.post("/api/v1/itr/ABCDE1234F/compute-and-stage", headers=hdr(), json={
        "digital_turnover": "24600000", "cash_turnover": "1400000"}).json()
    assert r["presumptive"]["eligible"] is False and "limit" in r["presumptive"]["reason"]
    assert client.post("/api/v1/itr/BADPAN/compute-and-stage", headers=hdr(), json={}).status_code == 422


def test_refund_pathway_blocks_itr_u(client):
    r = client.get("/api/v1/refund-pathway", headers=hdr(), params={"ay_start_year": 2024, "today": "2026-11-07"}).json()
    assert r["pathway"] == "SEC_119_2B" and r["itr_u_allowed"] is False


def test_sandbox_storyline_endpoint_runs_all_agents_and_the_gate():
    from fastapi.testclient import TestClient
    from taxsetu_api.main import create_app
    c = TestClient(create_app(b"s"))
    assert "TaxSetu AI" in c.get("/").text
    d = c.get("/api/v1/demo/storyline").json()
    assert d["simulated"] and [s["agent"] for s in d["steps"]][-1] == "Human gate" and len(d["steps"]) == 6
    facts = {k: v for s in d["steps"] for k, v in s["facts"]}
    assert facts["Pay now (net base)"] == "Rs 98000.00" and facts["TDS u/s 194C withheld"] == "Rs 2000.00"
    assert facts["Wrong OTP"].startswith("REFUSED") and facts["Hash chain intact"] == "True"
    assert "Rs 1000" in facts["1-digit plate typo, invoice on file"].replace(",", "") and "72000" in facts["Same notice, NO invoice on file"]
    assert len(c.get("/api/v1/demo/storyline").json()["steps"]) == 6   # fresh gate per call: repeatable, no leaked state
