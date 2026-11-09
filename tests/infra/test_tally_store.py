"""Tally outbox/alias/bridge/ledger store: one contract, two backends (memory always, Postgres under RLS when reachable)."""
import os
import uuid

import pytest
from taxsetu_api.store import Pg
from taxsetu_api.tally_store import MemoryTally, PgTally

APP = os.environ.get("DATABASE_URL_APP", "postgresql://taxsetu_app:taxsetu_app@localhost:5432/taxsetu")
ITEM = {"kind": "vouchers", "company": "Demo Co", "xml": "<ENVELOPE/>", "sha256": "a" * 64, "summary": {"count": 1}}


@pytest.fixture(params=["memory", "pg"])
def env(request):
    """(store, new_tenant) for each backend; the pg variant skips when no database with migration 0003 is reachable."""
    if request.param == "memory":
        return MemoryTally(), lambda: str(uuid.uuid4())
    psycopg = pytest.importorskip("psycopg", reason="psycopg not installed")
    try:
        with psycopg.connect(APP, connect_timeout=2) as c:
            c.execute("SELECT 1 FROM tally_outbox LIMIT 0")
    except Exception as e:
        pytest.skip(f"no live Postgres with migration 0003: {type(e).__name__}")
    pg = Pg(APP)

    def new_tenant():
        t = str(uuid.uuid4())
        with pg.tx(t) as c:
            c.execute("INSERT INTO tenants(tenant_id, legal_name, entity_type) VALUES (%s, %s, 'PROPRIETORSHIP')", (t, f"T {t[:6]}"))
        return t
    return PgTally(pg), new_tenant


def test_outbox_roundtrip_and_status_is_compare_and_set(env):
    s, nt = env
    t = nt()
    i = s.outbox_add(t, ITEM)
    assert i["status"] == "PENDING_APPROVAL" and s.outbox_get(t, i["batch_id"])["sha256"] == "a" * 64
    assert s.set_status(t, i["batch_id"], "PENDING_APPROVAL", "APPROVED", approved_by="OWNER") is True
    assert s.set_status(t, i["batch_id"], "PENDING_APPROVAL", "APPROVED", approved_by="OWNER") is False      # second approval loses
    assert [x["batch_id"] for x in s.outbox_list(t, "APPROVED")] == [i["batch_id"]]
    assert s.set_status(t, i["batch_id"], "APPROVED", "POSTED", ack={"ok": True, "created": 1}) is True
    assert s.outbox_get(t, i["batch_id"])["ack"]["created"] == 1


def test_tenants_cannot_see_each_others_rows(env):
    s, nt = env
    a, b = nt(), nt()
    i = s.outbox_add(a, ITEM)
    s.alias_put(a, "sharma", "Rent Paid")
    s.ledgers_replace(a, [{"name": "Cash", "parent": "Cash-in-Hand", "gstin": ""}])
    br = s.bridge_add(a, "Demo Co")
    assert s.outbox_get(b, i["batch_id"]) is None and s.outbox_list(b) == []
    assert s.aliases(b) == {} and s.ledgers(b) == [] and s.bridge_list(b) == [] and s.bridge_get(b, br["bridge_id"]) is None
    assert s.set_status(b, i["batch_id"], "PENDING_APPROVAL", "APPROVED") is False                              # cannot act on a foreign batch
    assert s.bridge_update(b, br["bridge_id"], revoked=True) is False


def test_alias_upsert_and_ledger_replace(env):
    s, nt = env
    t = nt()
    s.alias_put(t, "sharma", "Rent Paid")
    s.alias_put(t, "sharma", "Professional Fees")
    assert s.aliases(t) == {"sharma": "Professional Fees"}
    s.ledgers_replace(t, [{"name": "A", "parent": "P"}, {"name": "B", "parent": "P"}])
    s.ledgers_replace(t, [{"name": "C", "parent": "P"}])
    assert [l["name"] for l in s.ledgers(t)] == ["C"]


def test_bridge_pairing_is_single_use(env):
    s, nt = env
    t = nt()
    br = s.bridge_add(t, "Demo Co")
    assert s.bridge_update(t, br["bridge_id"], expect_paired=False, paired=True, host="PC-1") is True
    assert s.bridge_update(t, br["bridge_id"], expect_paired=False, paired=True, host="PC-2") is False        # code already used
    got = s.bridge_get(t, br["bridge_id"])
    assert got["paired"] and got["host"] == "PC-1" and not got["revoked"]
    assert s.bridge_update(t, br["bridge_id"], revoked=True) and s.bridge_get(t, br["bridge_id"])["revoked"]
