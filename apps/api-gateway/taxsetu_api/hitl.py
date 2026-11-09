"""HITL non-repudiation gate (FR-025). Agents can only stage; filing needs a single-use human OTP bound to the draft hash."""
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field

from .audit import AuditLog
from .portal import MockPortalProvider, PortalError, sign_approval
from .store import MemoryDrafts

OTP_TTL_S = 300


def canonical_sha256(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass
class Draft:
    draft_id: str
    tenant_id: str
    kind: str
    payload: dict
    sha256: str
    status: str = "DRAFT_STAGED"       # DRAFT_STAGED -> FILED_VERIFIED
    otp_hash: str | None = None
    otp_expires: float = 0.0
    ack: dict = field(default_factory=dict)
    version: int = 0                    # optimistic-lock counter used by the Postgres store


class AgentTools:
    """The ONLY surface handed to agents: stage and read. No file/approve method exists on it (Level-0 actions)."""

    def __init__(self, gate: "HitlGate"):
        self._gate = gate

    def stage(self, tenant_id: str, kind: str, payload: dict) -> dict:
        return self._gate._stage(tenant_id, kind, payload)

    def get(self, tenant_id: str, draft_id: str) -> dict:
        d = self._gate._owned(tenant_id, draft_id)
        return {"draft_id": d.draft_id, "kind": d.kind, "status": d.status, "payload_sha256": d.sha256}


class HitlGate:
    def __init__(self, secret: bytes, audit: AuditLog | None = None, clock=time.time, drafts=None, portal=None):
        self._secret, self.audit, self._clock = secret, audit or AuditLog(), clock
        self._drafts = drafts or MemoryDrafts()     # MemoryDrafts or store.PgDrafts: get(tenant, id) / save(draft)
        self._portal = portal or MockPortalProvider(secret)      # a live GSP provider is injected only when its credentials are configured
        self.agent_tools = AgentTools(self)

    def _owned(self, tenant_id: str, draft_id: str) -> Draft:
        d = self._drafts.get(tenant_id, draft_id)
        if d is None:                                   # same error for missing and foreign -> no tenant probing
            raise PortalError("draft not found")
        return d

    def _stage(self, tenant_id: str, kind: str, payload: dict) -> dict:
        errs = self._portal.validate(kind, payload)
        if errs:
            raise PortalError("; ".join(errs))
        d = Draft(str(uuid.uuid4()), tenant_id, kind, payload, canonical_sha256(payload))
        self._drafts.save(d)
        self.audit.append(tenant_id, "AGENT", "RETSAVE", draft_id=d.draft_id, payload_sha256=d.sha256)
        return {"draft_id": d.draft_id, "payload_sha256": d.sha256, "status": d.status}

    # --- human-side API (called only from the authenticated /hitl routes) ------------------------------------
    def request_otp(self, tenant_id: str, draft_id: str) -> str:
        """Mock EVC/Aadhaar OTP. In production the OTP is issued by the portal/UIDAI to the owner's own phone/Aadhaar."""
        d = self._owned(tenant_id, draft_id)
        otp = f"{secrets.randbelow(10**6):06d}"
        d.otp_hash = hashlib.sha256((otp + d.sha256).encode()).hexdigest()
        d.otp_expires = self._clock() + OTP_TTL_S
        self._drafts.save(d)
        self.audit.append(tenant_id, "OWNER", "OTP_ISSUED", draft_id=draft_id)
        return otp

    def authorize(self, tenant_id: str, draft_id: str, payload_sha256: str, otp: str, role: str = "OWNER",
                  verification_mode: str = "EVC_OTP") -> dict:
        d = self._owned(tenant_id, draft_id)
        if d.status == "FILED_VERIFIED":
            raise PortalError("already filed")           # no double filing
        if not hmac.compare_digest(payload_sha256, canonical_sha256(d.payload)):
            self.audit.append(tenant_id, role, "FILING_REJECTED", draft_id=draft_id, reason="payload hash mismatch")
            raise PortalError("payload changed since approval request")
        ok = d.otp_hash and self._clock() <= d.otp_expires and hmac.compare_digest(
            d.otp_hash, hashlib.sha256((otp + d.sha256).encode()).hexdigest())
        d.otp_hash = None                                 # single use, whether right or wrong
        self._drafts.save(d)                              # burn BEFORE filing; a concurrent loser fails on the version check
        if not ok:
            self.audit.append(tenant_id, role, "FILING_REJECTED", draft_id=draft_id, reason="bad or expired OTP")
            raise PortalError("invalid or expired OTP")
        d.ack = self._portal.file(d.kind, d.payload, d.draft_id, d.sha256, sign_approval(self._secret, d.draft_id, d.sha256), tenant_id=tenant_id)
        if d.ack.get("final") is False:
            # Saved at the portal but not filed (a live GSP cannot file: that needs the taxpayer's EVC/DSC). Never mark it filed.
            self._drafts.save(d)
            self.audit.append(tenant_id, role, "RETFILE_HITL", draft_id=draft_id, payload_sha256=d.sha256,
                              verification_method=verification_mode, portal_ack=d.ack["ack_no"], filed=False)
            return {"status": "SAVED_AT_PORTAL_AWAITING_EVC", **d.ack}
        d.status = "FILED_VERIFIED"
        self._drafts.save(d)
        self.audit.append(tenant_id, role, "RETFILE_HITL", draft_id=draft_id, payload_sha256=d.sha256,
                          verification_method=verification_mode, portal_ack=d.ack["ack_no"])
        return {"status": d.status, **d.ack}

    def edit_draft(self, tenant_id: str, draft_id: str, payload: dict) -> dict:
        """Inline edit (CA/owner): re-hashes, which invalidates any outstanding OTP."""
        d = self._owned(tenant_id, draft_id)
        if d.status == "FILED_VERIFIED":
            raise PortalError("already filed")
        d.payload, d.sha256, d.otp_hash = payload, canonical_sha256(payload), None
        self._drafts.save(d)
        self.audit.append(tenant_id, "CA_OR_OWNER", "DRAFT_EDITED", draft_id=draft_id, payload_sha256=d.sha256)
        return {"draft_id": draft_id, "payload_sha256": d.sha256}
