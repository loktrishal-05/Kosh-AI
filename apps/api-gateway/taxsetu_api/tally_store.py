"""Storage for the Tally autopilot: approval outbox, learned aliases, bridges, synced ledger list.
Memory (tests, sandbox) and Postgres (RLS, via store.Pg) share one interface; every method takes the tenant first.
Status changes are compare-and-set (`set_status`) so two concurrent approvals/acks cannot both win."""
import json
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryTally:
    def __init__(self):
        self._outbox, self._aliases, self._bridges, self._ledgers = {}, {}, {}, {}

    # --- outbox -----------------------------------------------------------------------------------------------
    def outbox_add(self, tenant: str, item: dict) -> dict:
        item = {**item, "batch_id": item.get("batch_id") or str(uuid.uuid4()), "tenant_id": tenant, "status": "PENDING_APPROVAL",
                "approved_by": None, "ack": {}, "created_at": _now()}
        self._outbox[item["batch_id"]] = item
        return dict(item)

    def outbox_get(self, tenant: str, batch_id: str) -> dict | None:
        i = self._outbox.get(batch_id)
        return dict(i) if i and i["tenant_id"] == tenant else None            # foreign == missing

    def outbox_list(self, tenant: str, status: str | None = None) -> list:
        rows = [dict(i) for i in self._outbox.values() if i["tenant_id"] == tenant and status in (None, i["status"])]
        return sorted(rows, key=lambda i: i["created_at"], reverse=True)

    def set_status(self, tenant: str, batch_id: str, expect: str, new: str, **fields) -> bool:
        i = self._outbox.get(batch_id)
        if not i or i["tenant_id"] != tenant or i["status"] != expect:
            return False
        i.update(status=new, **fields)
        return True

    # --- aliases ----------------------------------------------------------------------------------------------
    def aliases(self, tenant: str) -> dict:
        return dict(self._aliases.get(tenant, {}))

    def alias_put(self, tenant: str, alias: str, ledger: str) -> None:
        self._aliases.setdefault(tenant, {})[alias] = ledger

    # --- bridges ----------------------------------------------------------------------------------------------
    def bridge_add(self, tenant: str, company: str) -> dict:
        b = {"bridge_id": str(uuid.uuid4()), "tenant_id": tenant, "company": company, "host": None, "paired": False,
             "revoked": False, "last_seen": None, "created_at": _now()}
        self._bridges[b["bridge_id"]] = b
        return dict(b)

    def bridge_get(self, tenant: str, bridge_id: str) -> dict | None:
        b = self._bridges.get(bridge_id)
        return dict(b) if b and b["tenant_id"] == tenant else None

    def bridge_list(self, tenant: str) -> list:
        return [dict(b) for b in self._bridges.values() if b["tenant_id"] == tenant]

    def bridge_update(self, tenant: str, bridge_id: str, expect_paired: bool | None = None, **fields) -> bool:
        b = self._bridges.get(bridge_id)
        if not b or b["tenant_id"] != tenant or (expect_paired is not None and b["paired"] != expect_paired):
            return False
        b.update(fields)
        return True

    # --- ledgers ----------------------------------------------------------------------------------------------
    def ledgers_replace(self, tenant: str, ledgers: list) -> None:
        self._ledgers[tenant] = {l["name"]: l for l in ledgers}

    def ledgers(self, tenant: str) -> list:
        return list(self._ledgers.get(tenant, {}).values())


class PgTally:
    def __init__(self, pg):
        self.pg = pg

    _COLS = "batch_id::text, kind, company, xml, sha256, summary, status, approved_by, ack, created_at"

    @staticmethod
    def _item(r, tenant):
        return {"batch_id": r[0], "tenant_id": tenant, "kind": r[1], "company": r[2], "xml": r[3], "sha256": r[4].strip(),
                "summary": r[5], "status": r[6], "approved_by": r[7], "ack": r[8], "created_at": r[9].isoformat()}

    def outbox_add(self, tenant: str, item: dict) -> dict:
        bid = item.get("batch_id") or str(uuid.uuid4())
        with self.pg.tx(tenant) as c:
            c.execute("INSERT INTO tally_outbox (batch_id, tenant_id, kind, company, xml, sha256, summary) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (bid, tenant, item["kind"], item["company"], item["xml"], item["sha256"], json.dumps(item.get("summary", {}))))
        return self.outbox_get(tenant, bid)

    def outbox_get(self, tenant: str, batch_id: str) -> dict | None:
        try:
            uuid.UUID(batch_id)
        except ValueError:
            return None
        with self.pg.tx(tenant) as c:
            r = c.execute(f"SELECT {self._COLS} FROM tally_outbox WHERE batch_id = %s", (batch_id,)).fetchone()
        return r and self._item(r, tenant)

    def outbox_list(self, tenant: str, status: str | None = None) -> list:
        with self.pg.tx(tenant) as c:
            rows = c.execute(f"SELECT {self._COLS} FROM tally_outbox WHERE (%s::text IS NULL OR status = %s) ORDER BY created_at DESC",
                             (status, status)).fetchall()
        return [self._item(r, tenant) for r in rows]

    def set_status(self, tenant: str, batch_id: str, expect: str, new: str, **fields) -> bool:
        sets, args = ["status = %s"], [new]
        for k in ("approved_by", "ack"):
            if k in fields:
                sets.append(f"{k} = %s")
                args.append(json.dumps(fields[k]) if k == "ack" else fields[k])
        with self.pg.tx(tenant) as c:
            return c.execute(f"UPDATE tally_outbox SET {', '.join(sets)} WHERE batch_id = %s AND status = %s",
                             (*args, batch_id, expect)).rowcount == 1

    def aliases(self, tenant: str) -> dict:
        with self.pg.tx(tenant) as c:
            return dict(c.execute("SELECT alias, ledger FROM tally_aliases").fetchall())

    def alias_put(self, tenant: str, alias: str, ledger: str) -> None:
        with self.pg.tx(tenant) as c:
            c.execute("INSERT INTO tally_aliases (tenant_id, alias, ledger) VALUES (%s,%s,%s)"
                      " ON CONFLICT (tenant_id, alias) DO UPDATE SET ledger = EXCLUDED.ledger", (tenant, alias, ledger))

    def bridge_add(self, tenant: str, company: str) -> dict:
        bid = str(uuid.uuid4())
        with self.pg.tx(tenant) as c:
            c.execute("INSERT INTO tally_bridges (bridge_id, tenant_id, company) VALUES (%s,%s,%s)", (bid, tenant, company))
        return self.bridge_get(tenant, bid)

    _BCOLS = "bridge_id::text, company, host, paired, revoked, last_seen, created_at"

    @staticmethod
    def _bridge(r, tenant):
        return {"bridge_id": r[0], "tenant_id": tenant, "company": r[1], "host": r[2], "paired": r[3], "revoked": r[4],
                "last_seen": r[5] and r[5].isoformat(), "created_at": r[6].isoformat()}

    def bridge_get(self, tenant: str, bridge_id: str) -> dict | None:
        try:
            uuid.UUID(bridge_id)
        except ValueError:
            return None
        with self.pg.tx(tenant) as c:
            r = c.execute(f"SELECT {self._BCOLS} FROM tally_bridges WHERE bridge_id = %s", (bridge_id,)).fetchone()
        return r and self._bridge(r, tenant)

    def bridge_list(self, tenant: str) -> list:
        with self.pg.tx(tenant) as c:
            return [self._bridge(r, tenant) for r in c.execute(f"SELECT {self._BCOLS} FROM tally_bridges ORDER BY created_at DESC").fetchall()]

    def bridge_update(self, tenant: str, bridge_id: str, expect_paired: bool | None = None, **fields) -> bool:
        allowed = {"host", "paired", "revoked", "last_seen"}
        if not fields or set(fields) - allowed:
            raise ValueError("bad bridge fields")
        sets = ", ".join(f"{k} = %s" for k in fields)
        with self.pg.tx(tenant) as c:
            return c.execute(f"UPDATE tally_bridges SET {sets} WHERE bridge_id = %s AND (%s::boolean IS NULL OR paired = %s)",
                             (*fields.values(), bridge_id, expect_paired, expect_paired)).rowcount == 1

    def ledgers_replace(self, tenant: str, ledgers: list) -> None:
        with self.pg.tx(tenant) as c:
            c.execute("DELETE FROM tally_ledgers")
            for l in ledgers:
                c.execute("INSERT INTO tally_ledgers (tenant_id, name, parent, gstin) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                          (tenant, l["name"], l.get("parent", ""), l.get("gstin", "")))

    def ledgers(self, tenant: str) -> list:
        with self.pg.tx(tenant) as c:
            return [{"name": n, "parent": p, "gstin": g} for n, p, g in c.execute("SELECT name, parent, gstin FROM tally_ledgers ORDER BY name").fetchall()]
