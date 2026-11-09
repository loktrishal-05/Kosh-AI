"""Postgres-backed HITL drafts + audit log, against a real database under RLS. Skips when no Postgres/psycopg is reachable
(CI provides a service container; locally: `docker compose -f infra/docker-compose.yml up -d postgres`)."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from taxsetu_api import auth
from taxsetu_api.hitl import HitlGate
from taxsetu_api.main import create_app
from taxsetu_api.portal import PortalError
from taxsetu_api.store import Pg, PgAuditLog, PgDrafts

APP = os.environ.get("DATABASE_URL_APP", "postgresql://taxsetu_app:taxsetu_app@localhost:5432/taxsetu")
ADMIN = os.environ.get("DATABASE_URL_ADMIN", "postgresql://taxsetu:taxsetu@localhost:5432/taxsetu")   # table owner, used only to tamper
SECRET = b"pg-test-secret"


@pytest.fixture
def pg():
    psycopg = pytest.importorskip("psycopg", reason="psycopg not installed")
    try:
        psycopg.connect(APP, connect_timeout=2).close()
    except Exception as e:
        pytest.skip(f"no live Postgres: {type(e).__name__}")
    return Pg(APP)


def new_tenant(pg) -> str:
    t = str(uuid.uuid4())
    with pg.tx(t) as c:
        c.execute("INSERT INTO tenants(tenant_id, legal_name, entity_type) VALUES (%s, %s, 'PROPRIETORSHIP')", (t, f"Test {t[:6]}"))
    return t


def gate(pg, clock=None):
    return HitlGate(SECRET, audit=PgAuditLog(pg), drafts=PgDrafts(pg), **({"clock": clock} if clock else {}))


ITR = {"pan": "ABCDE1234F", "assessment_year": "2026-27", "form": "ITR-4"}


def test_draft_and_otp_survive_a_process_restart(pg):
    t = new_tenant(pg)
    a = gate(pg)
    d = a.agent_tools.stage(t, "ITR", ITR)
    otp = a.request_otp(t, d["draft_id"])
    b = gate(pg)                                              # a brand-new gate = a restarted server, sharing only the database
    ack = b.authorize(t, d["draft_id"], d["payload_sha256"], otp)
    assert ack["status"] == "FILED_VERIFIED" and ack["simulated"]
    with pytest.raises(PortalError, match="already filed"):
        gate(pg).authorize(t, d["draft_id"], d["payload_sha256"], otp)


def test_otp_is_single_use_across_instances(pg):
    t = new_tenant(pg)
    g = gate(pg)
    d = g.agent_tools.stage(t, "ITR", ITR)
    g.request_otp(t, d["draft_id"])
    with pytest.raises(PortalError, match="invalid or expired"):
        gate(pg).authorize(t, d["draft_id"], d["payload_sha256"], "000000")      # wrong guess burns the OTP...
    with pytest.raises(PortalError, match="invalid or expired"):
        gate(pg).authorize(t, d["draft_id"], d["payload_sha256"], "000000")      # ...so nothing can be retried against it


def test_edit_after_otp_voids_it(pg):
    t = new_tenant(pg)
    g = gate(pg)
    d = g.agent_tools.stage(t, "ITR", ITR)
    otp = g.request_otp(t, d["draft_id"])
    e = gate(pg).edit_draft(t, d["draft_id"], {**ITR, "form": "ITR-3"})
    with pytest.raises(PortalError):
        gate(pg).authorize(t, d["draft_id"], e["payload_sha256"], otp)


def test_tenant_cannot_see_or_use_anothers_draft(pg):
    a, b = new_tenant(pg), new_tenant(pg)
    d = gate(pg).agent_tools.stage(a, "ITR", ITR)
    for fn in (lambda: gate(pg).request_otp(b, d["draft_id"]), lambda: gate(pg).agent_tools.get(b, d["draft_id"])):
        with pytest.raises(PortalError, match="draft not found"):
            fn()
    with pytest.raises(PortalError, match="draft not found"):
        gate(pg).request_otp(a, str(uuid.uuid4()))          # same message for a draft that does not exist
    with pytest.raises(PortalError, match="draft not found"):
        gate(pg).request_otp(a, "not-a-uuid")


def test_concurrent_writers_lose_on_the_version_check(pg):
    t = new_tenant(pg)
    g = gate(pg)
    did = g.agent_tools.stage(t, "ITR", ITR)["draft_id"]
    repo = PgDrafts(pg)
    first, second = repo.get(t, did), repo.get(t, did)       # two workers load the same draft
    first.otp_hash = "a" * 64
    repo.save(first)
    second.otp_hash = "b" * 64
    with pytest.raises(PortalError, match="concurrently"):
        repo.save(second)                                     # stale write is refused, so one OTP cannot be spent twice


def test_audit_chain_persists_verifies_and_is_tenant_scoped(pg):
    a, b = new_tenant(pg), new_tenant(pg)
    g = gate(pg)
    d = g.agent_tools.stage(a, "ITR", ITR)
    g.authorize(a, d["draft_id"], d["payload_sha256"], g.request_otp(a, d["draft_id"]))
    g.agent_tools.stage(b, "ITR", ITR)
    ev = PgAuditLog(pg).events(a)
    assert [e["action"] for e in ev] == ["RETSAVE", "OTP_ISSUED", "RETFILE_HITL"]
    assert PgAuditLog(pg).verify(a) and PgAuditLog(pg).verify(b)
    assert len(PgAuditLog(pg).events(b)) == 1                # b sees only its own chain


def test_audit_tampering_is_detected_and_app_role_cannot_rewrite(pg):
    import psycopg
    t = new_tenant(pg)
    g = gate(pg)
    d = g.agent_tools.stage(t, "ITR", ITR)
    g.request_otp(t, d["draft_id"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with pg.tx(t) as c:
            c.execute("UPDATE hitl_approvals_and_audit_log SET actor_role = 'ADMIN'")      # append-only by grant
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with pg.tx(t) as c:
            c.execute("DELETE FROM hitl_approvals_and_audit_log")
    audit = PgAuditLog(pg)
    assert audit.verify(t)
    with psycopg.connect(ADMIN, autocommit=True) as admin:       # the table owner (not the app) rewrites history
        admin.execute("ALTER TABLE hitl_approvals_and_audit_log NO FORCE ROW LEVEL SECURITY")
        try:
            admin.execute("UPDATE hitl_approvals_and_audit_log SET body_json = replace(body_json, 'AGENT', 'OWNER') WHERE tenant_id = %s", (t,))
        finally:
            admin.execute("ALTER TABLE hitl_approvals_and_audit_log FORCE ROW LEVEL SECURITY")
    assert audit.verify(t) is False


def test_audit_appends_serialise_per_tenant(pg):
    from concurrent.futures import ThreadPoolExecutor
    t = new_tenant(pg)
    audit = PgAuditLog(pg)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: audit.append(t, "AGENT", "RETSAVE", n=i), range(24)))
    assert len(audit.events(t)) == 24 and audit.verify(t)        # advisory lock: the chain never forks under concurrency


def test_api_runs_end_to_end_on_postgres(pg, monkeypatch):
    monkeypatch.setenv("DATABASE_URL_APP", APP)
    t = new_tenant(pg)
    c = TestClient(create_app(SECRET, b"wa"))
    h = {"Authorization": "Bearer " + auth.encode({"role": "OWNER", "tenant_id": t}, SECRET)}
    assert c.get("/health").json()["store"] == "postgres"
    staged = c.post("/api/v1/itr/ABCDE1234F/compute-and-stage", headers=h,
                    json={"assessment_year": "2026-27", "digital_turnover": "2000000", "cash_turnover": "0"}).json()
    did, sha = staged["draft_id"], staged["payload_sha256"]
    otp = c.post(f"/api/v1/hitl/request-otp/{did}", headers=h).json()["mock_otp"]
    r = c.post("/api/v1/hitl/authorize-filing", headers=h, json={"draft_id": did, "payload_sha256": sha, "otp_or_signature": otp})
    assert r.status_code == 200 and r.json()["status"] == "FILED_VERIFIED"
    log = c.get("/api/v1/audit", headers=h).json()
    assert log["valid"] and [e["action"] for e in log["events"]] == ["RETSAVE", "OTP_ISSUED", "RETFILE_HITL"]


def test_unknown_tenant_gets_a_clear_404_not_a_500(pg, monkeypatch):
    """A valid token for a tenant with no tenants row used to hit the foreign key and return a bare 500."""
    monkeypatch.setenv("DATABASE_URL_APP", APP)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    c = TestClient(create_app(SECRET, b"wa"), raise_server_exceptions=False)
    ghost = {"Authorization": "Bearer " + auth.encode({"tenant_id": str(uuid.uuid4()), "role": "OWNER"}, SECRET)}
    d = {"vtype": "Payment", "date": "2026-04-01", "lines": [{"ledger": "Rent Paid", "amount": "1", "side": "Dr"},
                                                             {"ledger": "Bank Account", "amount": "1", "side": "Cr"}]}
    r = c.post("/api/v1/tally/batches", headers=ghost, json={"company": "X", "drafts": [d]})
    assert r.status_code == 404 and "not set up" in r.json()["detail"]
    assert c.get("/api/v1/tally/batches", headers=ghost).json() == {"batches": []}        # reads stay empty, never another tenant's rows


def test_tenant_onboarding_on_postgres_end_to_end(pg, monkeypatch):
    """Admin creates two real tenants; each can stage, neither can see the other's batch; an unknown tenant cannot even get a token."""
    monkeypatch.setenv("DATABASE_URL_APP", APP)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TAXSETU_ADMIN_KEY", "k" * 32)
    c = TestClient(create_app(SECRET, b"wa"), raise_server_exceptions=False)
    admin = {"x-admin-key": "k" * 32}
    mk = lambda n: c.post("/api/v1/auth/tenants", json={"legal_name": n}, headers=admin).json()["tenant_id"]
    a, b = mk("Alpha Traders"), mk("Beta Traders")
    tok = lambda t: {"Authorization": "Bearer " + c.post("/api/v1/auth/dev-token", json={"tenant_id": t, "role": "OWNER"}, headers=admin).json()["token"]}
    d = {"vtype": "Payment", "date": "2026-04-01", "lines": [{"ledger": "Rent Paid", "amount": "5", "side": "Dr"}, {"ledger": "Bank Account", "amount": "5", "side": "Cr"}]}
    staged = c.post("/api/v1/tally/batches", headers=tok(a), json={"company": "Alpha", "drafts": [d]})
    assert staged.status_code == 200
    bid = staged.json()["batch_id"]
    assert c.get(f"/api/v1/tally/batches/{bid}", headers=tok(b)).status_code == 404                    # real second tenant, real RLS
    assert c.get("/api/v1/tally/batches", headers=tok(b)).json() == {"batches": []}
    assert c.post(f"/api/v1/tally/batches/{bid}/approve", headers=tok(b), json={"payload_sha256": staged.json()["payload_sha256"]}).status_code == 404
    assert c.get(f"/api/v1/tally/batches/{bid}", headers=tok(a)).status_code == 200
    assert c.post("/api/v1/auth/dev-token", json={"tenant_id": str(uuid.uuid4()), "role": "OWNER"}, headers=admin).status_code == 404
    assert c.get("/api/v1/audit", headers=tok(a)).json()["valid"] is True
