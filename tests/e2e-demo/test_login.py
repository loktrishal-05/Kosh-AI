"""Demo sign-in: off unless the server turns it on; the one-click demo credentials work; wrong ones are refused and throttled; the token is a normal session."""
import uuid

import pytest
from fastapi.testclient import TestClient
from taxsetu_api import auth, login
from taxsetu_api.main import create_app

SECRET = b"login-test-secret-0123456789abcdef"


@pytest.fixture
def client(monkeypatch):
    for k in ("DATABASE_URL_APP", "DATABASE_URL", "TAXSETU_ADMIN_KEY", "ANTHROPIC_API_KEY", "TAXSETU_DEMO_LOGIN"):
        monkeypatch.delenv(k, raising=False)
    return TestClient(create_app(secret=SECRET, wa_secret=b"x"))


def test_the_demo_account_is_off_by_default(client):
    assert client.get("/api/v1/auth/demo-info").json() == {"enabled": False}
    r = client.post("/api/v1/auth/login", json={"username": login.DEMO_USER, "password": login.DEMO_PASSWORD})
    assert r.status_code == 401 and "token" not in r.text


def test_the_demo_button_flow_info_then_login_then_a_working_session(client, monkeypatch):
    monkeypatch.setenv("TAXSETU_DEMO_LOGIN", "1")
    info = client.get("/api/v1/auth/demo-info").json()
    assert info["enabled"] and info["label"] == "Demo admin" and info["username"] and info["password"]
    r = client.post("/api/v1/auth/login", json={"username": info["username"], "password": info["password"]})      # exactly what the button submits
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"] == {"name": "Demo Admin", "role": "OWNER", "demo": True} and body["expires_in_s"] == 8 * 3600
    claims = auth.decode(body["token"], SECRET)
    assert claims["tenant_id"] == login.DEMO_TENANT and claims["role"] == "OWNER"
    h = {"Authorization": "Bearer " + body["token"]}
    assert client.get("/api/v1/audit", headers=h).status_code == 200                              # an ordinary owner session on real routes
    assert client.get("/api/v1/books", headers=h).json() == {"books": []}
    assert client.get("/api/v1/gsp/status", headers=h).status_code == 200


def test_wrong_credentials_are_refused_with_one_generic_message(client, monkeypatch):
    monkeypatch.setenv("TAXSETU_DEMO_LOGIN", "1")
    for u, p in ((login.DEMO_USER, "wrong"), ("someone", login.DEMO_PASSWORD), (login.DEMO_USER.upper(), login.DEMO_PASSWORD), ("x", "y")):
        r = client.post("/api/v1/auth/login", json={"username": u, "password": p})
        assert r.status_code == 401 and r.json()["detail"] == "Wrong username or password."
    assert client.post("/api/v1/auth/login", json={"username": "", "password": ""}).status_code == 422


def test_repeated_wrong_passwords_are_throttled_and_a_good_login_still_resets(client, monkeypatch):
    monkeypatch.setenv("TAXSETU_DEMO_LOGIN", "1")
    for _ in range(login.MAX_FAILURES):
        assert client.post("/api/v1/auth/login", json={"username": login.DEMO_USER, "password": "nope"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": login.DEMO_USER, "password": login.DEMO_PASSWORD}).status_code == 429     # even the right one waits
    assert client.post("/api/v1/auth/login", json={"username": "other.user", "password": "nope"}).status_code == 401                      # other names are unaffected


def test_the_demo_session_cannot_see_another_tenants_data(client, monkeypatch):
    monkeypatch.setenv("TAXSETU_DEMO_LOGIN", "1")
    t = client.post("/api/v1/auth/login", json={"username": login.DEMO_USER, "password": login.DEMO_PASSWORD}).json()["token"]
    other = "Bearer " + auth.encode({"tenant_id": str(uuid.uuid4()), "role": "OWNER"}, SECRET)
    created = client.post("/api/v1/books", headers={"Authorization": other}, json={"name": "Private", "entity_type": "business", "period_start": "2026-04-01", "period_end": "2027-03-31"}).json()
    assert client.get(f"/api/v1/books/{created['book_id']}", headers={"Authorization": "Bearer " + t}).status_code == 404
