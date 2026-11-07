"""Dual-mode government portal gateway (FR-026). Only the Mock provider exists; Live needs licensed GSP/ERI credentials."""
import hashlib
import hmac
from typing import Protocol

REQUIRED = {  # minimal field-level validation standing in for the official GSTN/CBDT JSON schemas
    "GSTR1": ("gstin", "period"), "GSTR3B": ("gstin", "period"), "ITR": ("pan", "assessment_year", "form"),
    "EWB": ("gstin", "vehicle_no"),
}


class PortalError(Exception):
    pass


def sign_approval(secret: bytes, draft_id: str, payload_sha256: str) -> str:
    return hmac.new(secret, f"{draft_id}:{payload_sha256}".encode(), hashlib.sha256).hexdigest()


class PortalProvider(Protocol):
    def validate(self, kind: str, payload: dict) -> list: ...
    def file(self, kind: str, payload: dict, draft_id: str, payload_sha256: str, approval: str) -> dict: ...


class MockPortalProvider:
    """Simulated gst.gov.in / incometax.gov.in. Refuses any filing lacking a gate-signed approval bound to the payload hash."""

    def __init__(self, gate_secret: bytes):
        self._secret = gate_secret

    def validate(self, kind: str, payload: dict) -> list:
        return [f"missing field: {f}" for f in REQUIRED.get(kind, ()) if not payload.get(f)]

    def file(self, kind, payload, draft_id, payload_sha256, approval) -> dict:
        if not hmac.compare_digest(approval or "", sign_approval(self._secret, draft_id, payload_sha256)):
            raise PortalError("filing refused: no valid human approval token for this exact payload")
        errs = self.validate(kind, payload)
        if errs:
            raise PortalError("; ".join(errs))
        ref = hashlib.sha256(f"{kind}:{draft_id}:{payload_sha256}".encode()).hexdigest()[:15].upper()
        label = {"ITR": "ITR-V", "EWB": "EWB"}.get(kind, "ARN")
        return {"ack_type": label, "ack_no": f"SIM-{ref}", "simulated": True}
