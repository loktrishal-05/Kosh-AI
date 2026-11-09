"""Books store contract: memory always, Postgres under RLS when migration 0005 is applied. Closed books are frozen; nothing is deleted."""
import os
import uuid

import pytest
from taxsetu_api.books_store import MemoryBooks, PgBooks
from taxsetu_api.store import Pg

APP = os.environ.get("DATABASE_URL_APP", "postgresql://taxsetu_app:taxsetu_app@localhost:5432/taxsetu")
BOOK = {"name": "Test books", "entity_type": "business", "period_start": "2026-04-01", "period_end": "2027-03-31", "opening": {"cash": "100.00"}, "closing": {}}
E1 = {"date": "2026-05-01", "description": "Cash sales", "receipt": "500.00", "payment": "0.00", "mode": "cash", "party": "", "hint": ""}
E2 = {"date": "2026-05-02", "description": "Rent paid", "receipt": "0.00", "payment": "200.00", "mode": "bank", "party": "", "hint": ""}


@pytest.fixture(params=["memory", "pg"])
def env(request):
    if request.param == "memory":
        return MemoryBooks(), lambda: str(uuid.uuid4())
    psycopg = pytest.importorskip("psycopg", reason="psycopg not installed")
    try:
        with psycopg.connect(APP, connect_timeout=2) as c:
            c.execute("SELECT 1 FROM se_books LIMIT 0")
    except Exception as e:
        pytest.skip(f"no live Postgres with migration 0005: {type(e).__name__}")
    pg = Pg(APP)

    def new_tenant():
        t = str(uuid.uuid4())
        with pg.tx(t) as c:
            c.execute("INSERT INTO tenants(tenant_id, legal_name, entity_type) VALUES (%s, %s, 'PROPRIETORSHIP')", (t, f"T {t[:6]}"))
        return t
    return PgBooks(pg), new_tenant


def test_book_and_entries_roundtrip_in_order(env):
    s, nt = env
    t = nt()
    b = s.book_add(t, BOOK)
    assert b["status"] == "OPEN" and b["opening"] == {"cash": "100.00"}
    got = s.entry_add(t, b["book_id"], [E1, E2])
    assert [e["description"] for e in s.entry_list(t, b["book_id"])] == ["Cash sales", "Rent paid"] and len(got) == 2
    assert s.entry_list(t, b["book_id"])[0]["receipt"] == "500.00"


def test_void_keeps_history_and_closed_books_are_frozen(env):
    s, nt = env
    t = nt()
    b = s.book_add(t, BOOK)
    e = s.entry_add(t, b["book_id"], [E1, E2])[0]
    assert s.entry_void(t, b["book_id"], e["entry_id"], "typed twice") is True
    assert s.entry_void(t, b["book_id"], e["entry_id"], "again") is False                                  # already void
    assert len(s.entry_list(t, b["book_id"])) == 1 and len(s.entry_list(t, b["book_id"], include_void=True)) == 2
    assert s.book_update(t, b["book_id"], "OPEN", status="CLOSED", closed_report={"x": 1}) is True
    assert s.book_update(t, b["book_id"], "OPEN", status="CLOSED") is False                                 # closing twice loses
    assert s.entry_add(t, b["book_id"], [E1]) is None                                                       # frozen
    live = s.entry_list(t, b["book_id"])[0]
    assert s.entry_void(t, b["book_id"], live["entry_id"], "late change") is False                          # frozen
    assert s.book_get(t, b["book_id"])["closed_report"] == {"x": 1}


def test_tenants_cannot_see_or_touch_each_others_books(env):
    s, nt = env
    a, other = nt(), nt()
    b = s.book_add(a, BOOK)
    e = s.entry_add(a, b["book_id"], [E1])[0]
    assert s.book_get(other, b["book_id"]) is None and s.book_list(other) == [] and s.entry_list(other, b["book_id"]) == []
    assert s.entry_add(other, b["book_id"], [E2]) is None
    assert s.entry_void(other, b["book_id"], e["entry_id"], "nope") is False
    assert s.book_update(other, b["book_id"], "OPEN", opening={"cash": "1"}) is False
