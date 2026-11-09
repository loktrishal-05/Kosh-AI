"""Storage backends for the HITL gate: in-memory (default, tests, serverless sandbox) or PostgreSQL under row-level security.
Every Postgres call runs in its own transaction with `app.tenant_id` set, so the database - not this code - enforces isolation.
ponytail: one connection per operation (no pool) and a TEXT canonical-JSON body for hashing; add psycopg_pool when throughput matters."""
import json
import os
import time
import uuid
from contextlib import contextmanager
from urllib.parse import quote, urlsplit, urlunsplit

from .audit import GENESIS, AuditLog, canonical, h
from .portal import PortalError


class MemoryDrafts:
    def __init__(self):
        self._d = {}

    def get(self, tenant_id: str, draft_id: str):
        d = self._d.get(draft_id)
        return d if d is not None and d.tenant_id == tenant_id else None   # foreign == missing

    def save(self, d) -> None:
        self._d[d.draft_id] = d


class Pg:
    def __init__(self, url: str):
        import psycopg
        self._psycopg, self.url = psycopg, url

    @contextmanager
    def tx(self, tenant_id: str):
        uuid.UUID(tenant_id)                      # Postgres tenants are UUIDs; fail loudly instead of an opaque SQL error
        with self._psycopg.connect(self.url, prepare_threshold=None) as conn:     # commit on clean exit, rollback on exception
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
            yield conn


class PgDrafts:
    def __init__(self, pg: Pg):
        self.pg = pg

    def get(self, tenant_id: str, draft_id: str):
        from .hitl import Draft
        try:
            uuid.UUID(draft_id)
        except ValueError:
            return None
        with self.pg.tx(tenant_id) as c:
            r = c.execute("SELECT draft_id::text, tenant_id::text, kind, payload, payload_sha256, status, otp_hash, otp_expires, ack, version"
                          " FROM hitl_drafts WHERE draft_id = %s", (draft_id,)).fetchone()
        return r and Draft(r[0], r[1], r[2], r[3], r[4].strip(), r[5], r[6] and r[6].strip(), r[7], r[8], r[9])

    def save(self, d) -> None:
        with self.pg.tx(d.tenant_id) as c:
            if d.version == 0 and not c.execute("SELECT 1 FROM hitl_drafts WHERE draft_id = %s", (d.draft_id,)).fetchone():
                c.execute("INSERT INTO hitl_drafts (draft_id, tenant_id, kind, payload, payload_sha256, status, otp_hash, otp_expires, ack)"
                          " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (d.draft_id, d.tenant_id, d.kind, json.dumps(d.payload, default=str), d.sha256, d.status, d.otp_hash,
                           d.otp_expires, json.dumps(d.ack, default=str)))
                return
            n = c.execute("UPDATE hitl_drafts SET payload=%s, payload_sha256=%s, status=%s, otp_hash=%s, otp_expires=%s, ack=%s,"
                          " version=version+1 WHERE draft_id=%s AND version=%s",
                          (json.dumps(d.payload, default=str), d.sha256, d.status, d.otp_hash, d.otp_expires,
                           json.dumps(d.ack, default=str), d.draft_id, d.version)).rowcount
            if n != 1:
                raise PortalError("draft changed concurrently; retry")      # lost the race: someone else already used/edited it
            d.version += 1


class PgAuditLog(AuditLog):
    """Per-tenant hash chain (a tenant can only see its own rows under RLS, so chains cannot span tenants)."""

    def __init__(self, pg: Pg):
        self.pg = pg

    def append(self, tenant_id: str, actor_role: str, action: str, **data) -> dict:
        body = {"tenant_id": tenant_id, "actor_role": actor_role, "action": action, "ts": time.time(), **data}
        text = canonical(body)
        with self.pg.tx(tenant_id) as c:
            c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (tenant_id,))     # serialise appends so the chain cannot fork
            r = c.execute("SELECT event_hash FROM hitl_approvals_and_audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            prev = r[0].strip() if r else GENESIS
            ev_hash = h(prev, text)
            c.execute("INSERT INTO hitl_approvals_and_audit_log (tenant_id, actor_role, action_type, payload_sha256, verification_method,"
                      " portal_ack_arn_irn, prev_event_hash, event_hash, body_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (tenant_id, actor_role, action, data.get("payload_sha256"), data.get("verification_method"),
                       data.get("portal_ack"), prev, ev_hash, text))
        return {**body, "prev_event_hash": prev, "event_hash": ev_hash}

    def _rows(self, tenant_id: str):
        with self.pg.tx(tenant_id) as c:
            return c.execute("SELECT body_json, prev_event_hash, event_hash FROM hitl_approvals_and_audit_log ORDER BY seq").fetchall()

    def events(self, tenant_id: str | None = None) -> list[dict]:
        if tenant_id is None:
            raise ValueError("Postgres audit log is tenant-scoped; pass tenant_id")
        return [{**json.loads(b), "prev_event_hash": p.strip(), "event_hash": e.strip()} for b, p, e in self._rows(tenant_id)]

    def verify(self, tenant_id: str | None = None) -> bool:
        if tenant_id is None:
            raise ValueError("Postgres audit log is tenant-scoped; pass tenant_id")
        prev = GENESIS
        for text, p, e in self._rows(tenant_id):
            if p.strip() != prev or e.strip() != h(prev, text):
                return False
            prev = e.strip()
        return True


def app_url() -> str | None:
    """DATABASE_URL_APP verbatim, else the platform's owner URL (Vercel/Neon `DATABASE_URL`) re-pointed at the RLS-bound `taxsetu_app` role
    using TAXSETU_APP_PASSWORD, so the owner credential is never what the API runs as."""
    url = os.environ.get("DATABASE_URL_APP")
    if url:
        return url
    base, pw = os.environ.get("DATABASE_URL"), os.environ.get("TAXSETU_APP_PASSWORD")
    if not (base and pw):
        return None
    u = urlsplit(base)
    host = (u.hostname or "") + (f":{u.port}" if u.port else "")
    return urlunsplit(u._replace(netloc=f"taxsetu_app:{quote(pw, safe='')}@{host}"))


def from_env():
    """(drafts, audit) backed by Postgres when an app-role URL is configured and psycopg is installed, else (None, None) = in-memory."""
    url = app_url()
    if not url:
        return None, None
    pg = Pg(url)
    return PgDrafts(pg), PgAuditLog(pg)
