"""Smoke test of the full Tally flow against a deployed API (Vercel + Neon): sign in, draft, stage, pair the REAL tally_bridge.py,
approve, post into a FAKE Tally on localhost:19000, then check audit, isolation and revocation.
Usage: E2E_ADMIN_KEY=... [TAXSETU_API=https://taxsetu-ai.vercel.app] [E2E_TENANT=<uuid of an existing tenant>] python scripts/tally_e2e.py
It leaves harmless residue (a POSTED batch, a revoked bridge, two synced ledger names) on the tenant it uses. Never prints tokens or keys."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API = os.environ.get("TAXSETU_API", "https://taxsetu-ai.vercel.app").rstrip("/")
TENANT = os.environ.get("E2E_TENANT", "00000000-0000-4000-8000-0000000000a1")
COMPANY = "E2E Demo Books"
BRIDGE = str(Path(__file__).resolve().parent.parent / "apps" / "tally-bridge" / "tally_bridge.py")
KEY = os.environ["E2E_ADMIN_KEY"]
results = []


def step(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    return ok


def call(method, path, body=None, token=None, headers=None):
    h = {"content-type": "application/json", **(headers or {})}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:200].decode(errors="replace")}


# ---- fake Tally on localhost -------------------------------------------------------------------------------------
imports, exports = [], []
SUCCESS = "<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED><ERRORS>0</ERRORS><EXCEPTIONS>0</EXCEPTIONS></RESPONSE>"


class Tally(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if b"<TALLYREQUEST>Export</TALLYREQUEST>" in body:
            exports.append(body)
            raw = (f'<ENVELOPE><LEDGER NAME="Rent Paid"><PARENT>Indirect Expenses</PARENT></LEDGER>'
                   f'<LEDGER NAME="Bank Account"><PARENT>Bank Accounts</PARENT></LEDGER></ENVELOPE>'
                   if b"List of Accounts" in body else f'<ENVELOPE><COMPANY NAME="{COMPANY}"/></ENVELOPE>')
        else:
            imports.append(body)
            raw = SUCCESS
        self.send_response(200)
        self.end_headers()
        self.wfile.write(raw.encode())


srv = HTTPServer(("127.0.0.1", 19000), Tally)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp())
cfg = tmp / "bridge.json"


def bridge(*args):
    p = subprocess.run([sys.executable, BRIDGE, "--config", str(cfg), *args], capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr).strip()


# ---- 1. sign in ---------------------------------------------------------------------------------------------------
s, r = call("POST", "/api/v1/auth/dev-token", {"tenant_id": TENANT, "role": "OWNER"}, headers={"x-admin-key": KEY})
if not step("admin key mints an owner token", s == 200 and "token" in r, f"http {s}"):
    sys.exit(1)
owner = r["token"]
s, _ = call("POST", "/api/v1/auth/dev-token", {"tenant_id": TENANT, "role": "OWNER"}, headers={"x-admin-key": "wrong" * 10})
step("wrong admin key refused", s == 401, f"http {s}")
s, _ = call("POST", "/api/v1/auth/dev-token", {"tenant_id": TENANT, "role": "BRIDGE"}, headers={"x-admin-key": KEY})
step("admin key cannot mint a machine role", s == 422, f"http {s}")

# ---- 2. draft from plain words, stage ----------------------------------------------------------------------------
s, e = call("POST", "/api/v1/tally/entry", {"text": "Paid 25000 rent to Sharma by cheque yesterday", "state_code": "29"}, owner)
step("sentence becomes a balanced draft (authenticated, Neon aliases)", s == 200 and e.get("draft"), f"http {s}")
s, b = call("POST", "/api/v1/tally/batches", {"company": COMPANY, "drafts": [e["draft"]]}, owner)
step("batch staged in Neon outbox", s == 200 and b.get("status") == "PENDING_APPROVAL", f"http {s}")
bid, sha = b["batch_id"], b["payload_sha256"]
s, got = call("GET", f"/api/v1/tally/batches/{bid}", owner and None, owner)
step("stored xml hashes to the approved hash", s == 200 and hashlib.sha256(got["xml"].encode()).hexdigest() == sha)
s, _ = call("POST", "/api/v1/tally/batches", {"company": COMPANY, "drafts": [{**e["draft"], "lines": [{"ledger": "Suspense A/c", "amount": "1", "side": "Dr"}, {"ledger": "Bank Account", "amount": "1", "side": "Cr"}]}]}, owner)
step("suspense entry refused", s == 422, f"http {s}")

# ---- 3. pair the real bridge ------------------------------------------------------------------------------------
s, br = call("POST", "/api/v1/tally/bridges", {"company": COMPANY}, owner)
step("pairing code issued", s == 200 and "pairing_code" in br, f"http {s}")
rc, out = bridge("pair", "--api", API, "--code", br["pairing_code"])
step("bridge paired", rc == 0, out[:80])
c = json.loads(cfg.read_text())
c["tally_url"] = "http://127.0.0.1:19000"
cfg.write_text(json.dumps(c))
s, _ = call("POST", "/api/v1/tally/bridge/pair", {"code": br["pairing_code"], "host": "again"})
step("pairing code is single-use", s == 409, f"http {s}")

rc, out = bridge("selftest")
step("bridge selftest passes against fake Tally", rc == 0, out[-90:])
time.sleep(1)
s, led = call("GET", "/api/v1/tally/ledgers", None, owner)
step("ledger list synced up to Neon", s == 200 and {l["name"] for l in led["ledgers"]} >= {"Rent Paid", "Bank Account"}, f"{len(led.get('ledgers', []))} ledgers")

# ---- 4. nothing moves before approval ----------------------------------------------------------------------------
rc, out = bridge("once")
step("bridge posts nothing before approval", rc == 0 and not imports, f"imports={len(imports)}")
s, _ = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": "0" * 64}, owner)
step("approving a different hash is refused", s == 409, f"http {s}")
s, ap = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, owner)
step("owner approves the exact hash", s == 200 and ap.get("status") == "APPROVED", f"http {s}")
s, _ = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, owner)
step("second approval refused", s == 409, f"http {s}")

# ---- 5. bridge posts, cloud learns the result ------------------------------------------------------------------------
rc, out = bridge("once")
step("bridge cycle succeeded", rc == 0, out[-90:])
step("fake Tally received exactly the approved bytes", len(imports) == 1 and hashlib.sha256(imports[0]).hexdigest() == sha, f"imports={len(imports)}")
s, fin = call("GET", f"/api/v1/tally/batches/{bid}", None, owner)
step("batch is POSTED with Tally's counters", s == 200 and fin["status"] == "POSTED" and fin["ack"].get("created") == 1, fin.get("status", "?"))
rc, out = bridge("once")
step("rerun does not double-post", rc == 0 and len(imports) == 1, f"imports={len(imports)}")

# ---- 6. audit + isolation + revocation ------------------------------------------------------------------------------
s, log = call("GET", "/api/v1/audit", None, owner)
acts = {x["action"] for x in log.get("events", [])}
step("audit chain valid and complete", s == 200 and log.get("valid") is True and {"TALLY_BATCH_STAGED", "TALLY_BATCH_APPROVED", "BRIDGE_PAIRED", "TALLY_BATCH_POSTED"} <= acts, f"valid={log.get('valid')}")
btok = c["bridge_token"]
step("bridge token cannot read the audit log", call("GET", "/api/v1/audit", None, btok)[0] == 403)
step("bridge token cannot approve", call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, btok)[0] == 403)
ghost = call("POST", "/api/v1/auth/dev-token", {"tenant_id": "00000000-0000-4000-8000-0000000000b2", "role": "OWNER"}, headers={"x-admin-key": KEY})[1]["token"]
step("a different tenant gets 404 for this batch", call("GET", f"/api/v1/tally/batches/{bid}", None, ghost)[0] == 404)
step("a different tenant sees none of our batches", call("GET", "/api/v1/tally/batches", None, ghost)[1] == {"batches": []})
step("unknown tenant gets a clear 404 on write, not a 500", call("POST", "/api/v1/tally/batches", {"company": "X", "drafts": [e["draft"]]}, ghost)[0] == 404)
s, _ = call("DELETE", f"/api/v1/tally/bridges/{br['bridge_id']}", None, owner)
step("owner revokes the bridge", s == 200, f"http {s}")
step("revoked bridge is cut off", call("GET", "/api/v1/tally/bridge/pending", None, btok)[0] == 401)

print(f"\n{sum(results)}/{len(results)} steps passed")
sys.exit(0 if all(results) else 1)
