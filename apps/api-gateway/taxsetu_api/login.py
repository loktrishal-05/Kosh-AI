"""Sign-in for the evaluation demo.

One built-in DEMO ACCOUNT, switched on only when the server has TAXSETU_DEMO_LOGIN=1. Its username and password are public on purpose (the sign-in page shows them and the
"Demo admin" button fills them in), and it can only reach the shared demo workspace (one seeded tenant), so it grants nothing about any real client's data.

For real use, replace `authenticate` with a lookup in a user store (hashed passwords) or an identity provider (OIDC / mobile OTP) and leave TAXSETU_DEMO_LOGIN unset:
the routes, the token format, the role checks and the workbench's sign-in page stay as they are.
"""
import hmac
import os
import time

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import auth

DEMO_TENANT = "00000000-0000-4000-8000-0000000000a1"        # the sandbox tenant seeded by the migrations
DEMO_USER, DEMO_PASSWORD = "demo.admin", "Demo@2026"
SESSION_TTL_S = 8 * 3600
MAX_FAILURES, WINDOW_S = 10, 300


def demo_enabled() -> bool:
    return os.environ.get("TAXSETU_DEMO_LOGIN", "").strip().lower() in ("1", "true", "yes", "on")


def authenticate(username: str, password: str) -> dict | None:
    """Claims for a valid login, else None. THE place a real user store or identity provider plugs in."""
    same = hmac.compare_digest(username.encode(), DEMO_USER.encode()) & hmac.compare_digest(password.encode(), DEMO_PASSWORD.encode())
    if demo_enabled() and same:
        return {"tenant_id": DEMO_TENANT, "role": "OWNER", "name": "Demo Admin", "demo": True}
    return None


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


def mount(app, *, secret: bytes, tenant_exists, clock=time.time) -> None:
    failures: dict = {}                       # username -> (count, window start); in memory, per process

    @app.get("/api/v1/auth/demo-info", tags=["auth"])
    def demo_info():
        """Tells the sign-in page whether to offer the one-click demo and what to fill in. Nothing secret: it only answers when the demo account is on."""
        if not demo_enabled():
            return {"enabled": False}
        return {"enabled": True, "label": "Demo admin", "username": DEMO_USER, "password": DEMO_PASSWORD}

    @app.post("/api/v1/auth/login", tags=["auth"])
    def login(b: LoginIn):
        key = b.username.strip().lower()[:80]
        count, start = failures.get(key, (0, clock()))
        if clock() - start > WINDOW_S:
            count, start = 0, clock()
        if count >= MAX_FAILURES:
            raise HTTPException(429, "Too many wrong attempts. Wait a few minutes and try again.")
        claims = authenticate(b.username.strip(), b.password)
        if claims is None:
            failures[key] = (count + 1, start)
            raise HTTPException(401, "Wrong username or password.")
        failures.pop(key, None)
        if not tenant_exists(claims["tenant_id"]):
            raise HTTPException(503, "The demo workspace is not set up on this server yet.")
        token = auth.encode({"tenant_id": claims["tenant_id"], "role": claims["role"], "name": claims["name"]}, secret, ttl_s=SESSION_TTL_S)
        return {"token": token, "expires_in_s": SESSION_TTL_S, "user": {"name": claims["name"], "role": claims["role"], "demo": bool(claims.get("demo"))}}
