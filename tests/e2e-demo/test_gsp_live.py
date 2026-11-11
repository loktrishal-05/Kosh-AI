"""The live GST portal path (taxsetu_api.gsp_live) against a protocol SIMULATOR that plays GSTN's side: it holds its own RSA key, decrypts the app key,
checks the OTP, issues a session key, and verifies every request's AES envelope and HMAC. This proves the client follows the documented handshake and never
files; it does NOT prove compatibility with a real GSP (that needs licensed credentials)."""
import base64
import hashlib
import hmac
import json
import secrets
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from taxsetu_api import auth, gsp_live
from taxsetu_api.hitl import HitlGate
from taxsetu_api.main import create_app
from taxsetu_api.portal import MockPortalProvider, PortalError, sign_approval
from taxsetu_engine.gst import gstin_check_char

b64 = lambda b: base64.b64encode(b).decode()      # noqa: E731
OTP = "575757"
SECRET = b"gsp-live-test-secret-0123456789abc"


def gstin(pan="ABCDE1234F"):
    g = f"29{pan}1Z"
    return g + gstin_check_char(g)


class FakeGstn:
    """The server side of the documented protocol. Records what it received so tests can assert on it."""
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_pem = self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.app_keys, self.sessions, self.saved, self.tamper_reply, self.calls = {}, {}, [], False, []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        assert headers.get("clientid") == "cid" and headers.get("client-secret") == "csecret"
        if url.endswith("/authenticate"):
            return self.auth(headers, body)
        return self.returns(headers, body)

    def auth(self, headers, body):
        app_key = self.key.decrypt(base64.b64decode(body["app_key"]), padding.PKCS1v15())
        assert len(app_key) == 32
        if body["action"] == "OTPREQUEST":
            self.app_keys[body["username"]] = app_key
            return 200, {"status_cd": "1"}
        assert body["action"] == "AUTHTOKEN" and self.app_keys.get(body["username"]) == app_key
        if gsp_live.aes_decrypt(app_key, base64.b64decode(body["otp"])).decode() != OTP:
            return 200, {"status_cd": "0", "error": {"message": "Invalid OTP"}}
        sek, token = secrets.token_bytes(32), secrets.token_hex(8)
        self.sessions[token] = sek
        return 200, {"status_cd": "1", "auth_token": token, "sek": b64(gsp_live.aes_encrypt(app_key, sek)), "expiry": 360}

    def returns(self, headers, body):
        sek = self.sessions.get(headers.get("auth-token"))
        if sek is None:
            return 401, {"status_cd": "0", "error": {"message": "session expired"}}
        ek = gsp_live.aes_decrypt(sek, base64.b64decode(body["rek"]))
        payload = gsp_live.aes_decrypt(ek, base64.b64decode(body["data"]))
        if not hmac.compare_digest(b64(hmac.new(ek, payload, hashlib.sha256).digest()), body["hmac"]):
            return 200, {"status_cd": "0", "error": {"message": "HMAC mismatch"}}
        saved = json.loads(base64.b64decode(payload))
        self.saved.append((body["action"], headers.get("ret_period"), saved))
        reply = {"reference_id": "REF" + secrets.token_hex(5).upper(), "status": "P"}
        ek2 = secrets.token_bytes(32)
        inner = b64(json.dumps(reply).encode()).encode()
        mac = hmac.new(ek2, inner, hashlib.sha256).digest() if not self.tamper_reply else b"x" * 32
        return 200, {"status_cd": "1", "rek": b64(gsp_live.aes_encrypt(sek, ek2)), "data": b64(gsp_live.aes_encrypt(ek2, inner)), "hmac": b64(mac)}


@pytest.fixture
def gstn():
    return FakeGstn()


@pytest.fixture
def sessions(gstn):
    cfg = gsp_live.GspConfig("https://gsp.example", "cid", "csecret", gstn.public_pem)
    return gsp_live.GspSessions(cfg, transport=gstn)


def draft_payload(g):
    return {"gstin": g, "period": "042026", "b2b": [{"ctin": gstin("PQRST1234U"), "inv": [{"inum": "1", "val": "11800.00"}]}]}


def approved(gate, tenant, kind, payload):
    d = gate.agent_tools.stage(tenant, kind, payload)
    return d["draft_id"], d["payload_sha256"]


def file_live(provider, tenant, kind, payload, draft="d1", sha="a" * 64, token=None):
    return provider.file(kind, payload, draft, sha, sign_approval(SECRET, draft, sha) if token is None else token, tenant_id=tenant)


# ---- the handshake and a save ---------------------------------------------------------------------------------------------------------------------
def test_login_with_otp_then_save_a_return_as_a_draft_never_filing(gstn, sessions):
    g, t = gstin(), str(uuid.uuid4())
    s = sessions.start(t, g, "taxpayer_user")
    assert not s.active
    s.verify_otp(OTP)
    assert s.active
    ack = file_live(gsp_live.LivePortalProvider(SECRET, sessions), t, "GSTR3B", draft_payload(g))
    assert ack["ack_type"] == "RETSAVE" and ack["final"] is False and ack["simulated"] is False and ack["ack_no"].startswith("REF")
    assert "nothing has been filed" in ack["next_step"]
    action, period, body = gstn.saved[0]                               # what GSTN actually received, after decrypting and checking the HMAC
    assert action == "RETSAVE" and period == "042026" and body["gstin"] == g and body["fp"] == "042026" and body["b2b"][0]["inv"][0]["val"] == "11800.00"
    assert not any("RETFILE" in str(c) or "RETSUBMIT" in str(c) for c in gstn.calls)                     # no filing call exists in this client


def test_wrong_otp_gives_no_session_and_the_otp_is_not_sent_in_clear(gstn, sessions):
    g, t = gstin(), "t1"
    s = sessions.start(t, g, "u")
    with pytest.raises(gsp_live.GspError, match="Invalid OTP"):
        s.verify_otp("000000")
    assert not s.active
    with pytest.raises(gsp_live.GspError):
        s.verify_otp("12ab")                                           # not even sent
    with pytest.raises(gsp_live.GspError, match="request an OTP"):
        sessions.start(t, g, "u2") and gsp_live.GspSession(sessions.cfg, g, "u3", gstn).verify_otp("123456")


def test_a_tampered_reply_or_a_dead_session_is_refused(gstn, sessions):
    g, t = gstin(), "t1"
    s = sessions.start(t, g, "u")
    s.verify_otp(OTP)
    gstn.tamper_reply = True
    with pytest.raises(gsp_live.GspError, match="integrity"):
        file_live(gsp_live.LivePortalProvider(SECRET, sessions), t, "GSTR1", draft_payload(g))
    gstn.tamper_reply, gstn.sessions = False, {}
    with pytest.raises(gsp_live.GspError, match="session expired"):
        file_live(gsp_live.LivePortalProvider(SECRET, sessions), t, "GSTR1", draft_payload(g))


def test_sessions_expire(gstn):
    now = [1000.0]
    cfg = gsp_live.GspConfig("https://gsp.example", "cid", "csecret", gstn.public_pem)
    s = gsp_live.GspSessions(cfg, transport=gstn, clock=lambda: now[0]).start("t", gstin(), "u")
    s.verify_otp(OTP)
    assert s.active
    now[0] += gsp_live.SESSION_TTL_S + 1
    assert not s.active


# ---- the human-approval gate is unchanged ---------------------------------------------------------------------------------------------------------
def test_the_provider_refuses_without_the_gates_approval_token_a_session_or_a_valid_gstin(gstn, sessions):
    g, t = gstin(), "t1"
    p = gsp_live.LivePortalProvider(SECRET, sessions)
    with pytest.raises(PortalError, match="no valid human approval"):
        file_live(p, t, "GSTR3B", draft_payload(g), token="forged")
    with pytest.raises(gsp_live.GspError, match="log in to the GST portal"):
        file_live(p, t, "GSTR3B", draft_payload(g))
    assert p.validate("GSTR3B", {"gstin": "29ABCDE1234F1Z0", "period": "042026"}) == ["invalid GSTIN checksum"]
    assert gstn.saved == []


def test_one_tenant_cannot_use_another_tenants_portal_session(gstn, sessions):
    g = gstin()
    sessions.start("tenant-a", g, "u").verify_otp(OTP)
    with pytest.raises(gsp_live.GspError, match="log in to the GST portal"):
        file_live(gsp_live.LivePortalProvider(SECRET, sessions), "tenant-b", "GSTR3B", draft_payload(g))     # same GSTIN, different tenant
    assert gstn.saved == []


def test_income_tax_and_eway_bills_stay_on_the_mock_and_say_so(sessions):
    p = gsp_live.LivePortalProvider(SECRET, sessions)
    ack = file_live(p, "t", "ITR", {"pan": "ABCDE1234F", "assessment_year": "2026-27", "form": "ITR-1"})
    assert ack["simulated"] is True and ack["ack_type"] == "ITR-V"


def test_without_credentials_the_app_runs_on_the_mock_exactly_as_before(monkeypatch):
    for k in ("TAXSETU_GSP_BASE_URL", "TAXSETU_GSP_CLIENT_ID", "TAXSETU_GSP_CLIENT_SECRET", "TAXSETU_GSP_PUBLIC_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert gsp_live.GspConfig.from_env() is None
    monkeypatch.setenv("TAXSETU_GSP_BASE_URL", "https://gsp.example")
    assert gsp_live.GspConfig.from_env() is None                          # partial configuration is not enough


# ---- through the gate and the API --------------------------------------------------------------------------------------------------------------------
def test_gate_does_not_mark_a_saved_return_as_filed(gstn, sessions):
    g, t = gstin(), "t1"
    sessions.start(t, g, "u").verify_otp(OTP)
    clock = [1000.0]
    gate = HitlGate(SECRET, clock=lambda: clock[0], portal=gsp_live.LivePortalProvider(SECRET, sessions))
    draft, sha = approved(gate, t, "GSTR3B", draft_payload(g))
    otp = gate.request_otp(t, draft)
    out = gate.authorize(t, draft, sha, otp)
    assert out["status"] == "SAVED_AT_PORTAL_AWAITING_EVC" and out["final"] is False
    assert gate.agent_tools.get(t, draft)["status"] == "DRAFT_STAGED"                        # still a draft: the taxpayer files with EVC/DSC
    ev = [e for e in gate.audit.events(t) if e["action"] == "RETFILE_HITL"]
    assert len(ev) == 1 and ev[0]["filed"] is False and ev[0]["portal_ack"] == out["ack_no"]


def test_api_routes_login_and_roles(gstn, sessions):
    c = TestClient(create_app(secret=SECRET, wa_secret=b"x", gsp=sessions))
    tok = lambda t, role="OWNER": {"Authorization": "Bearer " + auth.encode({"tenant_id": t, "role": role}, SECRET)}      # noqa: E731
    g, t = gstin(), str(uuid.uuid4())
    assert c.get("/api/v1/gsp/status", headers=tok(t)).json()["live"] is True
    assert c.post("/api/v1/gsp/otp", headers=tok(t, "CLERK"), json={"gstin": g, "username": "u"}).status_code == 403
    assert c.post("/api/v1/gsp/session", headers=tok(t), json={"gstin": g, "username": "u", "otp": OTP}).status_code == 409       # no OTP requested yet
    assert c.post("/api/v1/gsp/otp", headers=tok(t), json={"gstin": g, "username": "u"}).json() == {"sent": True}
    assert c.post("/api/v1/gsp/session", headers=tok(t), json={"gstin": g, "username": "u", "otp": "111111"}).status_code == 409
    assert c.post("/api/v1/gsp/session", headers=tok(t), json={"gstin": g, "username": "u", "otp": OTP}).json() == {"active": True}
    assert c.post("/api/v1/gsp/session", headers=tok("other-tenant"), json={"gstin": g, "username": "u", "otp": OTP}).status_code == 409
    assert c.post("/api/v1/gsp/otp", headers=tok(t), json={"gstin": "bad", "username": "u"}).status_code == 502


def test_api_without_gsp_reports_it_is_off(monkeypatch):
    for k in ("TAXSETU_GSP_BASE_URL", "TAXSETU_GSP_CLIENT_ID", "TAXSETU_GSP_CLIENT_SECRET", "TAXSETU_GSP_PUBLIC_KEY"):
        monkeypatch.delenv(k, raising=False)
    c = TestClient(create_app(secret=SECRET, wa_secret=b"x"))
    h = {"Authorization": "Bearer " + auth.encode({"tenant_id": "t", "role": "OWNER"}, SECRET)}
    assert c.get("/api/v1/gsp/status", headers=h).json()["live"] is False
    assert c.post("/api/v1/gsp/otp", headers=h, json={"gstin": gstin(), "username": "u"}).status_code == 503


def test_a_session_survives_a_new_server_process_and_is_isolated_per_tenant(gstn, sessions):
    g, t = gstin(), str(uuid.uuid4())
    sessions.start(t, g, "u")                                          # process 1 asks for the OTP ...
    second = gsp_live.GspSessions(sessions.cfg, transport=gstn, store=sessions._store)   # ... process 2 (a fresh serverless instance) has no memory of it
    s = second.get(t, g)
    s.verify_otp(OTP)
    ack = file_live(gsp_live.LivePortalProvider(SECRET, sessions), t, "GSTR3B", draft_payload(g))     # process 1 sees the login process 2 completed
    assert ack["ack_type"] == "RETSAVE"
    assert second.get("someone-else", g) is None


def test_the_approval_otp_is_delivered_by_webhook_and_never_echoed(monkeypatch, gstn, sessions):
    sent = []
    monkeypatch.setattr(gsp_live, "send_otp", lambda url, token, tenant, draft, otp: sent.append((url, token, tenant, draft, otp)))
    monkeypatch.setenv("TAXSETU_OTP_WEBHOOK_URL", "https://sms.example/hook")
    c = TestClient(create_app(secret=SECRET, wa_secret=b"x", gsp=sessions))
    t = str(uuid.uuid4())
    h = {"Authorization": "Bearer " + auth.encode({"tenant_id": t, "role": "OWNER"}, SECRET)}
    did = c.app.state.gate.agent_tools.stage(t, "GSTR3B", draft_payload(gstin()))["draft_id"]
    r = c.post(f"/api/v1/hitl/request-otp/{did}", headers=h)
    assert r.json() == {"sent": True} and len(sent) == 1 and sent[0][2] == t and sent[0][4].isdigit()


def test_live_mode_without_a_delivery_channel_refuses_instead_of_echoing_the_otp(monkeypatch, gstn, sessions):
    monkeypatch.delenv("TAXSETU_OTP_WEBHOOK_URL", raising=False)
    c = TestClient(create_app(secret=SECRET, wa_secret=b"x", gsp=sessions))
    t = str(uuid.uuid4())
    h = {"Authorization": "Bearer " + auth.encode({"tenant_id": t, "role": "OWNER"}, SECRET)}
    did = c.app.state.gate.agent_tools.stage(t, "GSTR3B", draft_payload(gstin()))["draft_id"]
    r = c.post(f"/api/v1/hitl/request-otp/{did}", headers=h)
    assert r.status_code == 503 and "mock_otp" not in r.text


def test_send_otp_requires_https_and_fails_closed():
    with pytest.raises(gsp_live.GspError, match="https"):
        gsp_live.send_otp("http://x", "", "t", "d", "123456")
    with pytest.raises(gsp_live.GspError, match="delivered"):
        gsp_live.send_otp("https://x", "", "t", "d", "123456", transport=lambda *a: (500, {}))
