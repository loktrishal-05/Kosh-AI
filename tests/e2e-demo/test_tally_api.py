"""Tally autopilot over HTTP: sandbox, stage -> approve exact hash -> bridge pair/pending/ack, and the ways it must refuse."""
import hashlib
import hmac
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from taxsetu_api import auth
from taxsetu_api.main import create_app
from taxsetu_engine.tally_models import Line, VoucherDraft, draft_to_dict

SECRET = b"tally-api-test-secret-0123456789"
D = Decimal


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_APP", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TAXSETU_ADMIN_KEY", raising=False)
    return TestClient(create_app(secret=SECRET, wa_secret=b"x"))


def tok(tenant, role="OWNER", **extra):
    return {"Authorization": "Bearer " + auth.encode({"tenant_id": tenant, "role": role, **extra}, SECRET)}


def payment(ledger="Rent Paid", amount="1000", **kw):
    v = VoucherDraft("Payment", date(2026, 4, 1), (Line(ledger, D(amount), "Dr"), Line("Bank Account", D(amount), "Cr")),
                     party="Sharma", narration="April rent", **kw)
    return draft_to_dict(v)


def staged(client, tenant, drafts=None, **body):
    r = client.post("/api/v1/tally/batches", headers=tok(tenant), json={"company": "Demo Co", "drafts": drafts or [payment()], **body})
    return r


def paired_bridge(client, tenant, company="Demo Co"):
    code = client.post("/api/v1/tally/bridges", headers=tok(tenant), json={"company": company}).json()
    r = client.post("/api/v1/tally/bridge/pair", json={"code": code["pairing_code"], "host": "PC-1"})
    assert r.status_code == 200, r.text
    return code["bridge_id"], r.json(), code["pairing_code"]


# ---- sandbox ------------------------------------------------------------------------------------------------------
def test_sandbox_understands_a_plain_sentence(client):
    r = client.post("/api/v1/tally/sandbox/entry", json={"text": "Paid 25000 rent to Sharma by cheque yesterday", "today": "2026-04-10"}).json()
    d = r["draft"]
    assert d["vtype"] == "Payment" and r["plain"].startswith("You paid Rs 25,000.00")
    assert "to Rent Paid" not in r["plain"] and "recorded under Rent Paid" in r["plain"]
    assert sum(Decimal(l["amount"]) for l in d["lines"] if l["side"] == "Dr") == sum(Decimal(l["amount"]) for l in d["lines"] if l["side"] == "Cr")
    assert ET.fromstring(r["xml_preview"]).tag == "ENVELOPE"


def test_sandbox_asks_instead_of_guessing(client):
    r = client.post("/api/v1/tally/sandbox/entry", json={"text": "paid rent to Sharma"}).json()
    assert r["draft"] is None and r["questions"]


def test_sandbox_bank_statement_flags_unknowns_for_review(client):
    csv = "Date,Narration,Debit,Credit,Balance\n01/04/2026,UPI/123456789012/RANDOM PERSON/okaxis,500.00,,9500.00\n02/04/2026,SALARY APR,,50000.00,59500.00\n"
    r = client.post("/api/v1/tally/sandbox/bank-statement", json={"csv": csv}).json()
    assert r["summary"]["count"] == 2 and r["summary"]["needs_review"] >= 1
    assert any("Suspense A/c" in [l["ledger"] for l in d["lines"]] for d in r["drafts"])


def test_sandbox_starter_pack_and_download(client):
    r = client.get("/api/v1/tally/sandbox/starter-pack", params={"business_type": "trader", "state_code": "29"}).json()
    names = {l["name"] for l in r["ledgers"]}
    assert {"Input CGST", "Bank Account", "Rent Paid"} <= names and all(l["meaning"] for l in r["ledgers"])
    assert ET.fromstring(r["xml"]).tag == "ENVELOPE"
    assert client.get("/api/v1/tally/sandbox/starter-pack", params={"business_type": "spaceship"}).status_code == 422
    x = client.post("/api/v1/tally/sandbox/voucher-xml", json={"company": "Demo Co", "drafts": [payment()]}).json()
    assert x["count"] == 1 and "Rent Paid" in x["xml"]


def test_sandbox_limits_input_size(client):
    assert client.post("/api/v1/tally/sandbox/entry", json={"text": "x" * 1001}).status_code == 422
    assert client.post("/api/v1/tally/sandbox/bank-statement", json={"csv": "x" * 600_001}).status_code == 422


# ---- stage -> approve -> bridge -> ack -----------------------------------------------------------------------------------
def test_full_flow_posts_only_what_the_human_approved(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()
    sha = hashlib.sha256(client.get(f"/api/v1/tally/batches/{b['batch_id']}", headers=tok(t)).json()["xml"].encode()).hexdigest()
    assert b["payload_sha256"] == sha and b["status"] == "PENDING_APPROVAL"

    bid, paired, _ = paired_bridge(client, t)
    bridge = {"Authorization": "Bearer " + paired["bridge_token"]}
    assert client.get("/api/v1/tally/bridge/pending", headers=bridge).json()["items"] == []        # nothing before approval

    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": "0" * 64}).status_code == 409
    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": sha}).status_code == 200
    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": sha}).status_code == 409   # decided once

    item, = client.get("/api/v1/tally/bridge/pending", headers=bridge).json()["items"]
    assert item["id"] == b["batch_id"] and item["sha256"] == sha
    assert hmac.compare_digest(item["sig"], hmac.new(paired["signing_key"].encode(), sha.encode(), hashlib.sha256).hexdigest())
    assert hashlib.sha256(item["xml"].encode()).hexdigest() == sha

    ack = {"id": item["id"], "ok": True, "created": 1, "altered": 0, "errors": [], "response": "<RESPONSE/>"}
    assert client.post("/api/v1/tally/bridge/ack", headers=bridge, json=ack).json()["status"] == "POSTED"
    assert client.post("/api/v1/tally/bridge/ack", headers=bridge, json=ack).json()["status"] == "POSTED"      # retried ack is idempotent
    assert client.get("/api/v1/tally/bridge/pending", headers=bridge).json()["items"] == []
    got = client.get(f"/api/v1/tally/batches/{b['batch_id']}", headers=tok(t)).json()
    assert got["status"] == "POSTED" and got["ack"]["created"] == 1

    log = client.get("/api/v1/audit", headers=tok(t)).json()
    assert log["valid"] and {"TALLY_BATCH_STAGED", "TALLY_BATCH_APPROVED", "BRIDGE_PAIRED", "TALLY_BATCH_POSTED"} <= {e["action"] for e in log["events"]}


def test_failed_post_is_recorded_not_hidden(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()
    _, paired, _ = paired_bridge(client, t)
    bridge = {"Authorization": "Bearer " + paired["bridge_token"]}
    client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": b["payload_sha256"]})
    r = client.post("/api/v1/tally/bridge/ack", headers=bridge, json={"id": b["batch_id"], "ok": False, "errors": ["Ledger 'Rent Paid' does not exist"]})
    assert r.json()["status"] == "FAILED"
    assert "does not exist" in client.get(f"/api/v1/tally/batches/{b['batch_id']}", headers=tok(t)).json()["ack"]["errors"][0]


def test_ack_for_something_never_approved_is_refused(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()
    _, paired, _ = paired_bridge(client, t)
    bridge = {"Authorization": "Bearer " + paired["bridge_token"]}
    assert client.post("/api/v1/tally/bridge/ack", headers=bridge, json={"id": b["batch_id"], "ok": True}).status_code == 409
    assert client.get(f"/api/v1/tally/batches/{b['batch_id']}", headers=tok(t)).json()["status"] == "PENDING_APPROVAL"


def test_rejected_batch_never_reaches_the_bridge(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()
    _, paired, _ = paired_bridge(client, t)
    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/reject", headers=tok(t)).status_code == 200
    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": b["payload_sha256"]}).status_code == 409
    assert client.get("/api/v1/tally/bridge/pending", headers={"Authorization": "Bearer " + paired["bridge_token"]}).json()["items"] == []


def test_bridge_only_sees_batches_for_its_own_company(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()                                               # company "Demo Co"
    _, paired, _ = paired_bridge(client, t, company="Other Co")
    client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=tok(t), json={"payload_sha256": b["payload_sha256"]})
    assert client.get("/api/v1/tally/bridge/pending", headers={"Authorization": "Bearer " + paired["bridge_token"]}).json()["items"] == []


# ---- refusals -----------------------------------------------------------------------------------------------------------
def test_suspense_and_unbalanced_entries_cannot_be_staged(client):
    t = str(uuid.uuid4())
    assert staged(client, t, [payment("Suspense A/c")]).status_code == 422
    assert staged(client, t, [payment("Suspense A/c")], allow_suspense=True).status_code == 200
    bad = payment()
    bad["lines"][0]["amount"] = "999"
    assert staged(client, t, [bad]).status_code == 422
    bad = payment()
    bad["vtype"] = "Delete"
    assert staged(client, t, [bad]).status_code == 422
    assert staged(client, t, [{"vtype": "Payment"}]).status_code == 422


def test_other_tenants_and_clerks_cannot_decide_a_batch(client):
    a, b_ = str(uuid.uuid4()), str(uuid.uuid4())
    batch = staged(client, a).json()
    assert client.get(f"/api/v1/tally/batches/{batch['batch_id']}", headers=tok(b_)).status_code == 404
    assert client.post(f"/api/v1/tally/batches/{batch['batch_id']}/approve", headers=tok(b_), json={"payload_sha256": batch["payload_sha256"]}).status_code == 404
    assert client.post(f"/api/v1/tally/batches/{batch['batch_id']}/approve", headers=tok(a, "CLERK"), json={"payload_sha256": batch["payload_sha256"]}).status_code == 403
    assert client.get("/api/v1/tally/batches", headers=tok(b_)).json()["batches"] == []


def test_machine_tokens_cannot_use_human_routes_and_vice_versa(client):
    t = str(uuid.uuid4())
    b = staged(client, t).json()
    bridge_id, paired, code = paired_bridge(client, t)
    bridge = {"Authorization": "Bearer " + paired["bridge_token"]}
    for path in ("/api/v1/tally/batches", "/api/v1/audit", "/api/v1/tally/ledgers"):
        assert client.get(path, headers=bridge).status_code == 403
    assert client.post("/api/v1/hitl/authorize-filing", headers=bridge, json={"draft_id": "x", "payload_sha256": "y", "otp_or_signature": "z"}).status_code == 403
    assert client.post(f"/api/v1/tally/batches/{b['batch_id']}/approve", headers=bridge, json={"payload_sha256": b["payload_sha256"]}).status_code == 403
    assert client.get("/api/v1/tally/bridge/pending", headers=tok(t)).status_code == 403                    # an owner token is not a bridge
    assert client.get("/api/v1/tally/batches", headers={"Authorization": "Bearer " + code}).status_code == 403   # nor is a pairing code a login


def test_pairing_code_is_single_use_and_revocation_cuts_the_bridge_off(client):
    t = str(uuid.uuid4())
    bridge_id, paired, code = paired_bridge(client, t)
    assert client.post("/api/v1/tally/bridge/pair", json={"code": code, "host": "PC-2"}).status_code == 409
    assert client.post("/api/v1/tally/bridge/pair", json={"code": "not-a-real-code-xxxx"}).status_code == 401
    bridge = {"Authorization": "Bearer " + paired["bridge_token"]}
    assert client.get("/api/v1/tally/bridge/pending", headers=bridge).status_code == 200
    assert client.delete(f"/api/v1/tally/bridges/{bridge_id}", headers=tok(t)).status_code == 200
    assert client.get("/api/v1/tally/bridge/pending", headers=bridge).status_code == 401


def test_bridge_ledger_sync_feeds_setup(client):
    t = str(uuid.uuid4())
    _, paired, _ = paired_bridge(client, t)
    assert client.post("/api/v1/tally/bridge/ledgers", headers={"Authorization": "Bearer " + paired["bridge_token"]},
                       json={"ledgers": [{"name": "Cash", "parent": "Cash-in-Hand"}, {"name": "Bank Account", "parent": "Bank Accounts"}]}).json()["synced"] == 2
    full = client.get("/api/v1/tally/sandbox/starter-pack", params={"business_type": "trader", "state_code": "29"}).json()["ledgers"]
    s = client.post("/api/v1/tally/setup", headers=tok(t), json={"company": "Demo Co", "business_type": "trader", "state_code": "29"}).json()
    assert s["summary"]["count"] == len(full) - 2                          # ledgers Tally already has are not re-created


def test_alias_is_learned_per_tenant(client):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert client.post("/api/v1/tally/aliases", headers=tok(a), json={"party": "Mr. Sharma", "ledger": "Rent Paid"}).status_code == 200
    r = client.post("/api/v1/tally/entry", headers=tok(a), json={"text": "paid 5000 to Sharma by cheque", "today": "2026-04-10"}).json()
    assert r["draft"] and "Rent Paid" in [l["ledger"] for l in r["draft"]["lines"]]
    r2 = client.post("/api/v1/tally/entry", headers=tok(b), json={"text": "paid 5000 to Sharma by cheque", "today": "2026-04-10"}).json()
    assert not r2["draft"] or "Rent Paid" not in [l["ledger"] for l in r2["draft"]["lines"]]


def test_dev_token_is_off_unless_configured(client, monkeypatch):
    body = {"tenant_id": str(uuid.uuid4()), "role": "OWNER"}
    assert client.post("/api/v1/auth/dev-token", json=body, headers={"x-admin-key": "anything-at-all-long-enough-xx"}).status_code == 401
    monkeypatch.setenv("TAXSETU_ADMIN_KEY", "k" * 32)
    assert client.post("/api/v1/auth/dev-token", json=body, headers={"x-admin-key": "wrong" * 8}).status_code == 401
    r = client.post("/api/v1/auth/dev-token", json=body, headers={"x-admin-key": "k" * 32})
    assert r.status_code == 200 and client.get("/api/v1/tally/batches", headers={"Authorization": "Bearer " + r.json()["token"]}).status_code == 200
    assert client.post("/api/v1/auth/dev-token", json={**body, "role": "BRIDGE"}, headers={"x-admin-key": "k" * 32}).status_code == 422   # no minting machine roles


def test_tenant_creation_is_admin_only_and_audited(client, monkeypatch):
    body = {"legal_name": "Sunrise Traders", "entity_type": "PROPRIETORSHIP"}
    assert client.post("/api/v1/auth/tenants", json=body).status_code == 401                       # disabled while no admin key is configured
    monkeypatch.setenv("TAXSETU_ADMIN_KEY", "k" * 32)
    assert client.post("/api/v1/auth/tenants", json=body, headers={"x-admin-key": "wrong" * 8}).status_code == 401
    assert client.post("/api/v1/auth/tenants", json={**body, "entity_type": "COOPERATIVE"}, headers={"x-admin-key": "k" * 32}).status_code == 422
    r = client.post("/api/v1/auth/tenants", json=body, headers={"x-admin-key": "k" * 32})
    assert r.status_code == 200 and uuid.UUID(r.json()["tenant_id"])
    t = client.post("/api/v1/auth/dev-token", json={"tenant_id": r.json()["tenant_id"], "role": "OWNER"}, headers={"x-admin-key": "k" * 32}).json()["token"]
    log = client.get("/api/v1/audit", headers={"Authorization": "Bearer " + t}).json()
    assert log["valid"] and [e["action"] for e in log["events"]] == ["TENANT_CREATED"]
