"""Minimal HS256 JWT (stdlib). ponytail: swap for an IdP/OIDC library when real login (WhatsApp/mobile OTP) is wired."""
import base64
import hashlib
import hmac
import json
import time

ROLES = {"OWNER", "CLERK", "CA", "DRIVER", "EMPLOYEE", "BRIDGE", "PAIR"}      # BRIDGE/PAIR: Tally bridge machine tokens; no human route accepts them


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encode(claims: dict, secret: bytes, ttl_s: int = 3600) -> str:
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({**claims, "exp": int(time.time()) + ttl_s}).encode())
    sig = _b64(hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def decode(token: str, secret: bytes) -> dict:
    try:
        head, body, sig = token.split(".")
        good = _b64(hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good) or json.loads(_unb64(head)).get("alg") != "HS256":
            raise ValueError("bad signature")
        claims = json.loads(_unb64(body))
    except Exception as e:
        raise ValueError("invalid token") from e
    if claims.get("exp", 0) < time.time() or claims.get("role") not in ROLES or not claims.get("tenant_id"):
        raise ValueError("invalid token")
    return claims
