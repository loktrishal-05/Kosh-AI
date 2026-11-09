"""Storage for single-entry books kept over time: a book (one entity, one period) and its cash-book entries.
Memory and Postgres share one interface; every method takes the tenant first. Entries are never deleted: `entry_void` marks a line VOID with a reason.
A CLOSED book accepts no new entries and no voids (checked in the same transaction as the write)."""
import json
import uuid
from datetime import date, datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _money(x) -> str:
    from decimal import Decimal
    return format(Decimal(str(x or 0)).quantize(Decimal("0.01")), "f")


class MemoryBooks:
    def __init__(self):
        self._books, self._entries, self._seq = {}, {}, 0

    def book_add(self, tenant: str, rec: dict) -> dict:
        b = {**rec, "book_id": rec.get("book_id") or str(uuid.uuid4()), "tenant_id": tenant, "status": "OPEN", "closed_report": None, "created_at": _now()}
        self._books[b["book_id"]] = b
        self._entries[b["book_id"]] = []
        return json.loads(json.dumps(b))

    def book_get(self, tenant: str, book_id: str) -> dict | None:
        b = self._books.get(book_id)
        return json.loads(json.dumps(b)) if b and b["tenant_id"] == tenant else None

    def book_list(self, tenant: str) -> list:
        return sorted((json.loads(json.dumps(b)) for b in self._books.values() if b["tenant_id"] == tenant), key=lambda b: b["created_at"], reverse=True)

    def book_update(self, tenant: str, book_id: str, expect_status: str, **fields) -> bool:
        b = self._books.get(book_id)
        if not b or b["tenant_id"] != tenant or b["status"] != expect_status:
            return False
        b.update(json.loads(json.dumps(fields)))
        return True

    def entry_add(self, tenant: str, book_id: str, entries: list) -> list | None:
        b = self._books.get(book_id)
        if not b or b["tenant_id"] != tenant or b["status"] != "OPEN":
            return None
        out = []
        for e in entries:
            self._seq += 1
            rec = {**e, "entry_id": str(uuid.uuid4()), "book_id": book_id, "seq": self._seq, "status": "ACTIVE", "void_reason": None, "created_at": _now()}
            self._entries[book_id].append(rec)
            out.append(dict(rec))
        return out

    def entry_list(self, tenant: str, book_id: str, include_void: bool = False) -> list:
        b = self._books.get(book_id)
        if not b or b["tenant_id"] != tenant:
            return []
        return [dict(e) for e in self._entries[book_id] if include_void or e["status"] == "ACTIVE"]

    def entry_void(self, tenant: str, book_id: str, entry_id: str, reason: str) -> bool:
        b = self._books.get(book_id)
        if not b or b["tenant_id"] != tenant or b["status"] != "OPEN":
            return False
        for e in self._entries[book_id]:
            if e["entry_id"] == entry_id and e["status"] == "ACTIVE":
                e.update(status="VOID", void_reason=reason)
                return True
        return False


class PgBooks:
    def __init__(self, pg):
        self.pg = pg

    _B = "book_id::text, name, entity_type, period_start, period_end, opening, closing, status, closed_report, rolled_from::text, created_at"

    @staticmethod
    def _book(r, tenant):
        return {"book_id": r[0], "tenant_id": tenant, "name": r[1], "entity_type": r[2], "period_start": r[3].isoformat(), "period_end": r[4].isoformat(),
                "opening": r[5], "closing": r[6], "status": r[7], "closed_report": r[8], "rolled_from": r[9], "created_at": r[10].isoformat()}

    def book_add(self, tenant: str, rec: dict) -> dict:
        bid = rec.get("book_id") or str(uuid.uuid4())
        with self.pg.tx(tenant) as c:
            c.execute("INSERT INTO se_books (book_id, tenant_id, name, entity_type, period_start, period_end, opening, closing, rolled_from)"
                      " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (bid, tenant, rec["name"], rec["entity_type"], rec["period_start"], rec["period_end"], json.dumps(rec.get("opening", {})),
                       json.dumps(rec.get("closing", {})), rec.get("rolled_from")))
        return self.book_get(tenant, bid)

    def book_get(self, tenant: str, book_id: str) -> dict | None:
        try:
            uuid.UUID(book_id)
        except ValueError:
            return None
        with self.pg.tx(tenant) as c:
            r = c.execute(f"SELECT {self._B} FROM se_books WHERE book_id = %s", (book_id,)).fetchone()
        return r and self._book(r, tenant)

    def book_list(self, tenant: str) -> list:
        with self.pg.tx(tenant) as c:
            return [self._book(r, tenant) for r in c.execute(f"SELECT {self._B} FROM se_books ORDER BY created_at DESC").fetchall()]

    def book_update(self, tenant: str, book_id: str, expect_status: str, **fields) -> bool:
        allowed = {"opening", "closing", "status", "closed_report"}
        if not fields or set(fields) - allowed:
            raise ValueError("bad book fields")
        sets = ", ".join(f"{k} = %s" for k in fields)
        vals = [json.dumps(v) if k in ("opening", "closing", "closed_report") else v for k, v in fields.items()]
        with self.pg.tx(tenant) as c:
            return c.execute(f"UPDATE se_books SET {sets} WHERE book_id = %s AND status = %s", (*vals, book_id, expect_status)).rowcount == 1

    def entry_add(self, tenant: str, book_id: str, entries: list) -> list | None:
        with self.pg.tx(tenant) as c:
            ok = c.execute("SELECT 1 FROM se_books WHERE book_id = %s AND status = 'OPEN' FOR SHARE", (book_id,)).fetchone()
            if not ok:
                return None
            ids = []
            for e in entries:
                eid = str(uuid.uuid4())
                c.execute("INSERT INTO se_entries (entry_id, book_id, tenant_id, entry_date, description, receipt, payment, mode, party, hint)"
                          " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (eid, book_id, tenant, e["date"], e["description"], e["receipt"], e["payment"], e["mode"], e["party"], e["hint"]))
                ids.append(eid)
        return [x for x in self.entry_list(tenant, book_id, include_void=True) if x["entry_id"] in set(ids)]

    def entry_list(self, tenant: str, book_id: str, include_void: bool = False) -> list:
        try:
            uuid.UUID(book_id)
        except ValueError:
            return []
        with self.pg.tx(tenant) as c:
            rows = c.execute("SELECT entry_id::text, book_id::text, seq, entry_date, description, receipt, payment, mode, party, hint, status, void_reason, created_at"
                             " FROM se_entries WHERE book_id = %s AND (%s OR status = 'ACTIVE') ORDER BY seq", (book_id, include_void)).fetchall()
        return [{"entry_id": r[0], "book_id": r[1], "seq": r[2], "date": r[3].isoformat(), "description": r[4], "receipt": _money(r[5]), "payment": _money(r[6]),
                 "mode": r[7], "party": r[8], "hint": r[9], "status": r[10], "void_reason": r[11], "created_at": r[12].isoformat()} for r in rows]

    def entry_void(self, tenant: str, book_id: str, entry_id: str, reason: str) -> bool:
        try:
            uuid.UUID(entry_id)
        except ValueError:
            return False
        with self.pg.tx(tenant) as c:
            return c.execute("UPDATE se_entries SET status = 'VOID', void_reason = %s WHERE entry_id = %s AND book_id = %s AND status = 'ACTIVE'"
                             " AND EXISTS (SELECT 1 FROM se_books WHERE book_id = %s AND status = 'OPEN')", (reason, entry_id, book_id, book_id)).rowcount == 1
