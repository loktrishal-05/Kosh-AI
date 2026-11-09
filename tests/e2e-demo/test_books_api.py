"""Single-entry books over HTTP: the free sandbox, then keeping books over time (add, correct, close, roll over, send to Tally)."""
import json
import uuid
import xml.etree.ElementTree as ET
from decimal import Decimal as D
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from taxsetu_api import auth
from taxsetu_api.main import create_app

SECRET = b"books-api-test-secret-0123456789"
SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "samples" / "single_entry"


@pytest.fixture
def client(monkeypatch):
    for k in ("DATABASE_URL_APP", "DATABASE_URL", "TAXSETU_ADMIN_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    return TestClient(create_app(secret=SECRET, wa_secret=b"x"))


def tok(tenant, role="OWNER"):
    return {"Authorization": "Bearer " + auth.encode({"tenant_id": tenant, "role": role}, SECRET)}


def sample(name):
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def new_book(client, t, name="business_textbook", **over):
    s = sample(name)
    body = {k: s[k] for k in ("name", "entity_type", "period_start", "period_end", "opening", "closing")} | over
    r = client.post("/api/v1/books", headers=tok(t), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def add(client, t, book, entries, role="OWNER"):
    return client.post(f"/api/v1/books/{book['book_id']}/entries", headers=tok(t, role), json={"entries": entries})


def report(client, t, book):
    return client.get(f"/api/v1/books/{book['book_id']}/report", headers=tok(t)).json()["report"]


# ---- sandbox --------------------------------------------------------------------------------------------------------------------
def test_sandbox_lists_real_time_examples_and_converts_them(client):
    ex = client.get("/api/v1/books/sandbox/examples").json()["examples"]
    assert {e["id"] for e in ex} == {"business_textbook", "kirana_full_year", "nonprofit_club", "individual_freelancer"}
    book = client.get("/api/v1/books/sandbox/examples/business_textbook").json()["book"]
    r = client.post("/api/v1/books/sandbox/convert", json={"book": book}).json()
    assert r["statements"]["profit_loss"]["net_profit"] == "211000.00" and r["statements"]["balance_sheet"]["balanced"] and r["crosscheck"]["agrees"]
    assert client.get("/api/v1/books/sandbox/examples/../../etc/passwd").status_code in (404, 422)
    assert client.get("/api/v1/books/sandbox/examples/nope").status_code == 404


def test_sandbox_rejects_bad_input_clearly(client):
    book = sample("business_textbook")
    post = lambda b: client.post("/api/v1/books/sandbox/convert", json={"book": b}).status_code
    assert post({**book, "entity_type": "spaceship"}) == 422
    assert post({**book, "period_end": "2025-01-01"}) == 422
    assert post({**book, "opening": {"cash": "lots"}}) == 422
    assert post({**book, "opening": {"hacker": "1"}}) == 422
    assert post({**book, "entries": book["entries"] * 100}) == 422                                            # over the sandbox line limit
    assert post({**book, "entries": [{"date": "2026-04-02", "description": "x", "receipt": "5", "payment": "5"}]}) == 422
    assert post({**book, "entries": [{"date": "not a date", "description": "x", "receipt": "5"}]}) == 422
    csv = "Date,Particulars,Receipt,Payment\n05/04/2026,Cash sales,1500,\n06/04/2026,Shop rent,,500\n"
    parsed = client.post("/api/v1/books/sandbox/parse-csv", json={"csv": csv}).json()
    assert len(parsed["entries"]) == 2 and not parsed["errors"]


# ---- keeping books over time ------------------------------------------------------------------------------------------------------
def test_full_life_cycle_add_correct_close_rollover(client):
    t = str(uuid.uuid4())
    b = new_book(client, t)
    entries = [{k: v for k, v in e.items()} for e in sample("business_textbook")["entries"]]
    r = add(client, t, b, entries)
    assert r.status_code == 200 and r.json()["added"] == len(entries)
    rep = report(client, t, b)
    assert rep["statements"]["profit_loss"]["net_profit"] == "211000.00" and rep["crosscheck"]["agrees"]

    # a wrong line is corrected by voiding it (with a reason) and re-entering: nothing is ever deleted
    bad = add(client, t, b, [{"date": "2026-11-01", "description": "Shop rent paid", "payment": "6000", "mode": "bank"}]).json()["entries"][0]
    assert report(client, t, b)["statements"]["profit_loss"]["net_profit"] == "205000.00"
    assert client.post(f"/api/v1/books/{b['book_id']}/entries/{bad['entry_id']}/void", headers=tok(t), json={"reason": "typed twice"}).status_code == 200
    assert report(client, t, b)["statements"]["profit_loss"]["net_profit"] == "211000.00"
    assert client.post(f"/api/v1/books/{b['book_id']}/entries/{bad['entry_id']}/void", headers=tok(t), json={"reason": "again"}).status_code == 409
    every = client.get(f"/api/v1/books/{b['book_id']}/entries", headers=tok(t), params={"include_void": True}).json()["entries"]
    assert [e["status"] for e in every].count("VOID") == 1 and len(every) == len(entries) + 1

    closed = client.post(f"/api/v1/books/{b['book_id']}/close", headers=tok(t), json={})
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert client.post(f"/api/v1/books/{b['book_id']}/close", headers=tok(t), json={}).status_code == 409
    assert add(client, t, b, [{"date": "2026-12-01", "description": "x", "receipt": "1"}]).status_code == 409                       # a closed period is frozen
    assert client.put(f"/api/v1/books/{b['book_id']}/setup", headers=tok(t), json={"closing": {"stock": "1"}}).status_code == 409

    nxt = client.post(f"/api/v1/books/{b['book_id']}/rollover", headers=tok(t), json={}).json()
    assert nxt["period_start"] == "2027-04-01" and nxt["period_end"] == "2028-03-31" and nxt["rolled_from"] == b["book_id"]
    assert client.post(f"/api/v1/books/{b['book_id']}/rollover", headers=tok(t), json={}).status_code == 409                         # only once
    nrep = report(client, t, nxt)
    assert nrep["statements"]["balance_sheet"]["capital"]["opening"] == "309000.00"                                                # last year's closing capital
    assert any("stock" in q.lower() for q in nrep["questions"])                                                                    # a new period has no closing stock yet: it asks
    assert client.put(f"/api/v1/books/{nxt['book_id']}/setup", headers=tok(t), json={"closing": {"stock": "75000"}}).status_code == 200
    quiet = report(client, t, nxt)
    assert quiet["statements"]["profit_loss"]["net_profit"] == "5000.00"                                                           # last year's accrued rent reverses; still unpaid, so it shows as a credit
    assert client.put(f"/api/v1/books/{nxt['book_id']}/setup", headers=tok(t), json={"closing": {"stock": "75000", "outstanding_expenses": {"Rent Paid": "5000"}}}).status_code == 200
    nrep = report(client, t, nxt)
    assert D(nrep["statements"]["balance_sheet"]["total_assets"]) == D("354000.00")                                                # same assets carried over
    assert nrep["statements"]["balance_sheet"]["capital"]["closing"] == "309000.00" and nrep["statements"]["profit_loss"]["net_profit"] == "0.00"
    log = client.get("/api/v1/audit", headers=tok(t)).json()
    assert log["valid"] and {"BOOK_CREATED", "BOOK_ENTRIES_ADDED", "BOOK_ENTRY_VOIDED", "BOOK_CLOSED", "BOOK_ROLLED_OVER"} <= {e["action"] for e in log["events"]}


def test_close_is_blocked_until_doubts_are_answered(client):
    t = str(uuid.uuid4())
    b = new_book(client, t)
    add(client, t, b, sample("business_textbook")["entries"])
    add(client, t, b, [{"date": "2026-11-02", "description": "misc stuff", "payment": "100", "mode": "cash"}])      # the converter cannot tell what this is
    r = client.post(f"/api/v1/books/{b['book_id']}/close", headers=tok(t), json={})
    assert r.status_code == 409 and "need your attention" in r.json()["detail"]
    assert client.post(f"/api/v1/books/{b['book_id']}/close", headers=tok(t), json={"accept_review": True}).status_code == 200


def test_entries_are_validated_and_scoped_to_the_period(client):
    t = str(uuid.uuid4())
    b = new_book(client, t)
    assert add(client, t, b, [{"date": "2025-01-01", "description": "too early", "receipt": "5"}]).status_code == 422
    assert add(client, t, b, [{"date": "2026-05-01", "description": "both", "receipt": "5", "payment": "5"}]).status_code == 422
    assert add(client, t, b, [{"date": "2026-05-01", "description": "neither"}]).status_code == 422
    assert add(client, t, b, []).status_code == 422
    csv = "Date,Particulars,Receipt,Payment\n05/04/2026,Cash sales,1500,\n06/04/2026,Shop rent,,500\n"
    r = client.post(f"/api/v1/books/{b['book_id']}/entries", headers=tok(t), json={"csv": csv})
    assert r.status_code == 200 and r.json()["added"] == 2


def test_other_tenants_roles_and_unknown_books(client):
    a, other = str(uuid.uuid4()), str(uuid.uuid4())
    b = new_book(client, a)
    assert client.get(f"/api/v1/books/{b['book_id']}", headers=tok(other)).status_code == 404
    assert client.get("/api/v1/books", headers=tok(other)).json() == {"books": []}
    assert add(client, other, b, [{"date": "2026-05-01", "description": "x", "receipt": "1"}]).status_code == 404
    assert add(client, a, b, [{"date": "2026-05-01", "description": "x", "receipt": "1"}], role="EMPLOYEE").status_code == 200               # staff may enter
    assert client.post(f"/api/v1/books/{b['book_id']}/close", headers=tok(a, "EMPLOYEE"), json={}).status_code == 403                       # but not close
    assert client.get("/api/v1/books/not-a-uuid", headers=tok(a)).status_code == 404
    assert client.get("/api/v1/books", headers={}).status_code in (401, 403)
    bridge = {"Authorization": "Bearer " + auth.encode({"tenant_id": a, "role": "BRIDGE", "bridge_id": "x"}, SECRET)}
    assert client.get("/api/v1/books", headers=bridge).status_code == 403                                                                  # machine tokens cannot read books


def test_books_can_be_sent_to_tally_through_the_approval_queue(client):
    t = str(uuid.uuid4())
    b = new_book(client, t)
    add(client, t, b, sample("business_textbook")["entries"])
    r = client.post(f"/api/v1/books/{b['book_id']}/tally", headers=tok(t), json={"company": "Ravi General Stores"})
    assert r.status_code == 200, r.text
    staged = r.json()["staged"]
    assert staged[0]["what"] == "ledgers" and all(s["status"] == "PENDING_APPROVAL" for s in staged)
    vouchers = ET.fromstring(client.get(f"/api/v1/tally/batches/{staged[1]['batch_id']}", headers=tok(t)).json()["xml"])
    vs = list(vouchers.iter("VOUCHER"))
    assert len(vs) >= 10 and all(v.get("REMOTEID", "").startswith("ts-") for v in vs)
    for v in vs:
        amounts = [D(e.findtext("AMOUNT")) for e in v.iter("ALLLEDGERENTRIES.LIST")]
        assert sum(amounts) == 0, v.findtext("NARRATION")                                                                                # every voucher balances
    nothing_posted = client.get("/api/v1/tally/bridge/pending", headers=tok(t))
    assert nothing_posted.status_code == 403                                                                                              # staged only: nothing reaches Tally unapproved
