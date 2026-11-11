"""Live GST portal access through a GSP (GST Suvidha Provider), behind the same human-approval gate as the mock.

What this does: log a taxpayer in to the GST portal (OTP sent by GSTN to the taxpayer's own phone), keep the resulting session, and SAVE a GSTR-1 / GSTR-3B
draft (RETSAVE) and read its status. What it never does: file. Filing a return needs the taxpayer's EVC (or a DSC), which only the taxpayer can give on the portal
or in a DSC bridge, so a live "file" here returns ack_type RETSAVE with final=False and the gate does not mark the draft as filed.
Not provided: income tax (ERI). The ERI API specification is issued only after ERI registration and a data-transmission test, so ITR and e-way bills stay on the mock.

The session protocol follows what GSP vendors publish for the GSTN API: the client makes a random 256-bit app key and sends it RSA-encrypted with GSTN's public key;
the OTP is AES-256 encrypted with that app key; the reply carries an auth token and a session key (sek) encrypted with the app key; each later call encrypts its body with
a fresh key (ek), sends ek encrypted with sek, and an HMAC-SHA256 of the body. Field names and routes differ slightly between GSPs, so the routes and header names are configurable.
STATUS: tested against a protocol simulator (tests/e2e-demo/test_gsp_live.py), NOT against a real GSP: that needs licensed credentials this project does not have.
Secrets are read from the environment only and are never logged or returned.
"""
import base64
import hashlib
import hmac as _hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from taxsetu_engine import gst

from .portal import REQUIRED, MockPortalProvider, PortalError, sign_approval

LIVE_KINDS = ("GSTR1", "GSTR3B")
SESSION_TTL_S = 6 * 3600          # GSTN sessions last up to six hours; the server's own expiry, if shorter, wins


class GspError(PortalError):
    pass


# ---- crypto (the `cryptography` package, imported lazily so the rest of the API does not need it) -------------------------------------------------
def _aes(key: bytes, data: bytes, encrypt: bool) -> bytes:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if len(key) != 32:
        raise GspError("session key has the wrong length")
    c = Cipher(algorithms.AES(key), modes.ECB())               # the GSTN protocol specifies AES-256 in ECB mode with PKCS7 padding
    if encrypt:
        p, e = padding.PKCS7(128).padder(), c.encryptor()
        return e.update(p.update(data) + p.finalize()) + e.finalize()
    d, u = c.decryptor(), padding.PKCS7(128).unpadder()
    try:
        return u.update(d.update(data) + d.finalize()) + u.finalize()
    except ValueError:
        raise GspError("could not decrypt the portal's reply")


def aes_encrypt(key: bytes, data: bytes) -> bytes:
    return _aes(key, data, True)


def aes_decrypt(key: bytes, data: bytes) -> bytes:
    return _aes(key, data, False)


def rsa_encrypt(public_pem: bytes, data: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.x509 import load_pem_x509_certificate
    try:
        key = load_pem_public_key(public_pem)
    except ValueError:
        key = load_pem_x509_certificate(public_pem).public_key()      # GSTN distributes a certificate
    return key.encrypt(data, padding.PKCS1v15())


b64 = lambda b: base64.b64encode(b).decode()                       # noqa: E731
unb64 = lambda s: base64.b64decode(s, validate=True)               # noqa: E731


# ---- configuration -----------------------------------------------------------------------------------------------------------------------------
@dataclass
class GspConfig:
    base_url: str
    client_id: str
    client_secret: str
    public_key_pem: bytes
    ip_usr: str = "127.0.0.1"
    auth_path: str = "/taxpayerapi/v1.0/authenticate"
    return_path: str = "/taxpayerapi/v3.0/returns/{kind}"
    header_names: dict = field(default_factory=lambda: {"client_id": "clientid", "client_secret": "client-secret", "state": "state-cd", "ip": "ip-usr",
                                                        "txn": "txn", "gstin": "gstin", "period": "ret_period", "user": "username", "token": "auth-token"})

    @staticmethod
    def from_env():
        """None unless every credential is present: the app then runs on the mock exactly as before."""
        e = os.environ
        key = e.get("TAXSETU_GSP_PUBLIC_KEY", "")
        if key and "BEGIN" not in key and os.path.exists(key):
            key = open(key, encoding="utf-8").read()
        need = [e.get("TAXSETU_GSP_BASE_URL"), e.get("TAXSETU_GSP_CLIENT_ID"), e.get("TAXSETU_GSP_CLIENT_SECRET"), key]
        if not all(need):
            return None
        extra = {k: e[f"TAXSETU_GSP_{k.upper()}"] for k in ("auth_path", "return_path", "ip_usr") if e.get(f"TAXSETU_GSP_{k.upper()}")}
        return GspConfig(need[0].rstrip("/"), need[1], need[2], key.encode(), **extra)


def urllib_transport(method: str, url: str, headers: dict, body: dict | None) -> tuple:
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GspError("the GST portal could not be reached")


def send_otp(url: str, token: str, tenant_id: str, draft_id: str, otp: str, transport=urllib_transport) -> None:
    """Hand the approval OTP to the operator's SMS/WhatsApp gateway (a webhook that knows the tenant's owner phone). Fails closed: no delivery, no OTP."""
    if not url.startswith("https://"):
        raise GspError("the OTP delivery webhook must be https")
    status, _ = transport("POST", url, {"Authorization": f"Bearer {token}"} if token else {}, {"tenant_id": tenant_id, "draft_id": draft_id, "otp": otp})
    if not 200 <= status < 300:
        raise GspError("the OTP could not be delivered")


# ---- one taxpayer's portal session ---------------------------------------------------------------------------------------------------------------
class GspSession:
    def __init__(self, cfg: GspConfig, gstin: str, username: str, transport=urllib_transport, clock=time.time, on_change=None):
        if not gst.is_valid_gstin(gstin):
            raise GspError("invalid GSTIN")
        if not username or len(username) > 60 or any(ord(c) < 32 for c in username):
            raise GspError("invalid portal user name")
        self.cfg, self.gstin, self.username, self._send, self._clock = cfg, gstin, username, transport, clock
        self._app_key = b""
        self._token = ""
        self._sek = b""
        self._expires = 0.0
        self._on_change = on_change                                   # the session store saves every change, so any server process can pick the session up

    def to_state(self) -> bytes:
        return json.dumps({"gstin": self.gstin, "username": self.username, "app_key": b64(self._app_key), "token": self._token,
                           "sek": b64(self._sek), "expires": self._expires}).encode()

    @classmethod
    def from_state(cls, cfg: GspConfig, state: bytes, transport=urllib_transport, clock=time.time, on_change=None):
        d = json.loads(state)
        s = cls(cfg, d["gstin"], d["username"], transport, clock, on_change)
        s._app_key, s._token, s._sek, s._expires = unb64(d["app_key"]), d["token"], unb64(d["sek"]), float(d["expires"])
        return s

    def _save(self) -> None:
        if self._on_change:
            self._on_change(self)

    def _headers(self, extra: dict | None = None) -> dict:
        n = self.cfg.header_names
        h = {n["client_id"]: self.cfg.client_id, n["client_secret"]: self.cfg.client_secret, n["state"]: self.gstin[:2], n["ip"]: self.cfg.ip_usr,
             n["txn"]: secrets.token_hex(16), n["gstin"]: self.gstin, n["user"]: self.username}
        return {**h, **(extra or {})}

    def _post(self, path: str, headers: dict, body: dict) -> dict:
        status, data = self._send("POST", self.cfg.base_url + path, headers, body)
        if status != 200 or str(data.get("status_cd", "1")) == "0":
            err = data.get("error", {}) if isinstance(data.get("error"), dict) else {}
            raise GspError(f"the GST portal refused this: {str(err.get('message') or 'HTTP ' + str(status))[:160]}")
        return data

    @property
    def active(self) -> bool:
        return bool(self._token and self._sek and self._clock() < self._expires)

    def request_otp(self) -> None:
        """GSTN sends the OTP to the taxpayer's registered mobile; this process never sees it."""
        self._app_key = secrets.token_bytes(32)
        self._post(self.cfg.auth_path, self._headers(), {"action": "OTPREQUEST", "username": self.username, "app_key": b64(rsa_encrypt(self.cfg.public_key_pem, self._app_key))})
        self._save()

    def verify_otp(self, otp: str) -> None:
        if not self._app_key:
            raise GspError("request an OTP first")
        if not (otp.isdigit() and 4 <= len(otp) <= 8):
            raise GspError("the OTP is a number of 4 to 8 digits")
        r = self._post(self.cfg.auth_path, self._headers(), {"action": "AUTHTOKEN", "username": self.username, "app_key": b64(rsa_encrypt(self.cfg.public_key_pem, self._app_key)),
                                                              "otp": b64(aes_encrypt(self._app_key, otp.encode()))})
        try:
            self._sek = aes_decrypt(self._app_key, unb64(r["sek"]))
            self._token = str(r["auth_token"])
            self._expires = self._clock() + min(SESSION_TTL_S, float(r.get("expiry", 360)) * 60)
        except (KeyError, ValueError, TypeError):
            raise GspError("the portal's login reply was not understood")
        self._app_key = b""                                           # single use
        self._save()

    def call(self, action: str, kind: str, period: str, body: dict, method: str = "PUT") -> dict:
        """An encrypted, HMAC-signed call to a returns API. Returns the decrypted JSON reply."""
        if not self.active:
            raise GspError("the GST portal session is not active: the taxpayer must log in with the OTP first")
        ek = secrets.token_bytes(32)
        payload = b64(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
        envelope = {"action": action, "data": b64(aes_encrypt(ek, payload.encode())), "rek": b64(aes_encrypt(self._sek, ek)),
                    "hmac": b64(_hmac.new(ek, payload.encode(), hashlib.sha256).digest())}
        n = self.cfg.header_names
        reply = self._post(self.cfg.return_path.format(kind=kind.lower()), self._headers({n["token"]: self._token, n["period"]: period}), envelope)
        try:
            rek = aes_decrypt(self._sek, unb64(reply["rek"]))
            inner = aes_decrypt(rek, unb64(reply["data"]))
            if not _hmac.compare_digest(b64(_hmac.new(rek, inner, hashlib.sha256).digest()), str(reply.get("hmac", ""))):
                raise GspError("the portal's reply failed its integrity check")
            return json.loads(unb64(inner.decode()))
        except (KeyError, ValueError, TypeError):
            raise GspError("the portal's reply was not understood")


class MemorySessionStore:
    """Per-process (tests, a single long-running host). Use PgSessionStore wherever more than one process may serve a request, e.g. Vercel."""
    def __init__(self):
        self._d = {}

    def load(self, tenant: str, gstin: str):
        return self._d.get((tenant, gstin))

    def save(self, tenant: str, gstin: str, state: bytes, expires: float) -> None:
        self._d[(tenant, gstin)] = state


class PgSessionStore:
    """Portal sessions in Postgres (table gsp_sessions, RLS by tenant), sealed with Fernet under a key derived from the server secret: the database never holds a usable session key."""
    def __init__(self, pg, secret: bytes):
        from cryptography.fernet import Fernet
        self.pg, self._f = pg, Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"gsp-session|" + secret).digest()))

    def load(self, tenant: str, gstin: str):
        with self.pg.tx(tenant) as c:
            r = c.execute("SELECT state FROM gsp_sessions WHERE gstin = %s", (gstin,)).fetchone()
        return r and self._f.decrypt(r[0].encode())

    def save(self, tenant: str, gstin: str, state: bytes, expires: float) -> None:
        with self.pg.tx(tenant) as c:
            c.execute("INSERT INTO gsp_sessions (tenant_id, gstin, state, expires_at) VALUES (%s,%s,%s,to_timestamp(%s))"
                      " ON CONFLICT (tenant_id, gstin) DO UPDATE SET state = EXCLUDED.state, expires_at = EXCLUDED.expires_at, updated_at = now()",
                      (tenant, gstin, self._f.encrypt(state).decode(), expires or time.time() + SESSION_TTL_S))


class GspSessions:
    """Sessions per (tenant, GSTIN). A tenant can only use a session it created itself (the store is keyed, and in Postgres isolated, by tenant)."""
    def __init__(self, cfg: GspConfig, transport=urllib_transport, clock=time.time, store=None):
        self.cfg, self._transport, self._clock, self._store = cfg, transport, clock, store or MemorySessionStore()

    def _make(self, tenant: str, gstin: str, username: str = "", state: bytes | None = None) -> GspSession:
        def persist(s):
            self._store.save(tenant, s.gstin, s.to_state(), s._expires)
        if state is not None:
            return GspSession.from_state(self.cfg, state, self._transport, self._clock, persist)
        return GspSession(self.cfg, gstin, username, self._transport, self._clock, persist)

    def start(self, tenant: str, gstin: str, username: str) -> GspSession:
        s = self._make(tenant, gstin, username)
        s.request_otp()
        return s

    def get(self, tenant: str, gstin: str):
        state = self._store.load(tenant, gstin)
        return self._make(tenant, gstin, state=state) if state else None


# ---- the provider --------------------------------------------------------------------------------------------------------------------------------
class LivePortalProvider:
    """GSTR-1 / GSTR-3B through a GSP when the taxpayer has a live session; everything else stays on the mock, clearly marked simulated."""

    def __init__(self, gate_secret: bytes, sessions: GspSessions | None, fallback: MockPortalProvider | None = None):
        self._secret, self._sessions = gate_secret, sessions
        self._mock = fallback or MockPortalProvider(gate_secret)

    def validate(self, kind: str, payload: dict) -> list:
        errs = self._mock.validate(kind, payload)
        if kind in LIVE_KINDS and not errs and not gst.is_valid_gstin(str(payload.get("gstin", ""))):
            errs.append("invalid GSTIN checksum")
        return errs

    def file(self, kind, payload, draft_id, payload_sha256, approval, tenant_id: str = "") -> dict:
        if kind not in LIVE_KINDS or self._sessions is None:
            return self._mock.file(kind, payload, draft_id, payload_sha256, approval)
        if not _hmac.compare_digest(approval or "", sign_approval(self._secret, draft_id, payload_sha256)):
            raise PortalError("filing refused: no valid human approval token for this exact payload")
        errs = self.validate(kind, payload)
        if errs:
            raise PortalError("; ".join(errs))
        s = self._sessions.get(tenant_id, payload["gstin"])
        if s is None or not s.active:
            raise GspError("log in to the GST portal first: request the OTP for this GSTIN and enter it")
        body = {k: v for k, v in payload.items() if k not in ("gstin", "period")}
        reply = s.call("RETSAVE", kind, payload["period"], {"gstin": payload["gstin"], "fp": payload["period"], **body})
        ref = str(reply.get("reference_id") or reply.get("ref_id") or "")[:60]
        if not ref:
            raise GspError("the portal did not return a reference for the saved return")
        return {"ack_type": "RETSAVE", "ack_no": ref, "simulated": False, "final": False,
                "next_step": "Saved at the GST portal as a draft. The taxpayer must file it there with EVC or DSC; nothing has been filed."}
