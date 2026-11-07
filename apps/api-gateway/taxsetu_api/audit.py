"""Append-only, SHA-256 hash-chained audit log (NFR-007)."""
import hashlib
import json
import time

GENESIS = "0" * 64


def _h(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()


class AuditLog:
    # ponytail: in-memory list; persist to the hitl_approvals_and_audit_log table (Postgres) when the DB layer lands.
    def __init__(self):
        self._events: list[dict] = []

    def append(self, tenant_id: str, actor_role: str, action: str, **data) -> dict:
        prev = self._events[-1]["event_hash"] if self._events else GENESIS
        body = {"tenant_id": tenant_id, "actor_role": actor_role, "action": action, "ts": time.time(), **data}
        ev = {**body, "prev_event_hash": prev, "event_hash": _h(prev, body)}
        self._events.append(ev)
        return ev

    def events(self, tenant_id: str | None = None) -> list[dict]:
        return [dict(e) for e in self._events if tenant_id in (None, e["tenant_id"])]

    def verify(self) -> bool:
        prev = GENESIS
        for e in self._events:
            body = {k: v for k, v in e.items() if k not in ("prev_event_hash", "event_hash")}
            if e["prev_event_hash"] != prev or e["event_hash"] != _h(prev, body):
                return False
            prev = e["event_hash"]
        return True
