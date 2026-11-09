"""Smoke test of the full Tally flow against a deployed API (Vercel + Neon): sign in, draft, stage, pair the REAL tally_bridge.py,
approve, post into a FAKE Tally on localhost:19000 (default) or into a REAL TallyPrime (set TALLY_URL and E2E_COMPANY), then check audit, isolation and revocation.
Usage: E2E_ADMIN_KEY=... [TAXSETU_API=https://taxsetu-ai.vercel.app] python scripts/tally_e2e.py
It creates two throwaway tenants (admin endpoint) and leaves harmless residue on them: a POSTED batch, a revoked bridge, two synced ledger names. Never prints tokens or keys."""
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
TALLY_URL = os.environ.get("TALLY_URL", "")               # set (with E2E_COMPANY) to post into a real TallyPrime instead of the fake
LIVE = bool(TALLY_URL)
COMPANY = os.environ.get("E2E_COMPANY", "E2E Demo Books")
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


if not LIVE:
    srv = HTTPServer(("127.0.0.1", 19000), Tally)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
ENTRY_DATE = time.strftime("%d/%m/%Y", time.strptime(time.strftime("%Y-%m-02"), "%Y-%m-%d"))      # Tally Education mode only takes the 1st, 2nd and last day of a month


def tally_payments():
    """How many 25,000.00 payments the REAL Tally holds (live mode) or the fake received (default)."""
    if not LIVE:
        return len(imports)
    sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "packages" / "deterministic-tax-engine")]
    from datetime import date
    from taxsetu_engine import tallybooks as tb
    req = urllib.request.Request(TALLY_URL, data=tb.export_daybook_request(COMPANY, date.today(), date.today()).encode(), headers={"Content-Type": "text/xml; charset=utf-8"})
    rows = tb.parse_daybook_export(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
    return sum(1 for r in rows if r["vtype"] == "Payment" and r["amount"] == "25000.00")

tmp = Path(tempfile.mkdtemp())
cfg = tmp / "bridge.json"


def bridge(*args):
    p = subprocess.run([sys.executable, BRIDGE, "--config", str(cfg), *args], capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout + p.stderr).strip()


# ---- 0. two real tenants (onboarding endpoint) ---------------------------------------------------------------------
def make_tenant(name):
    s, r = call("POST", "/api/v1/auth/tenants", {"legal_name": name}, headers={"x-admin-key": KEY})
    return r.get("tenant_id") if s == 200 else None


stamp = time.strftime("%Y%m%d-%H%M%S")
TENANT, OTHER = make_tenant("E2E Alpha " + stamp), make_tenant("E2E Beta " + stamp)
if not step("admin creates two real tenants", TENANT and OTHER and TENANT != OTHER):
    sys.exit(1)
s, _ = call("POST", "/api/v1/auth/tenants", {"legal_name": "No Key Ltd"})
step("tenant creation without the admin key is refused", s == 401, f"http {s}")
s, _ = call("POST", "/api/v1/auth/dev-token", {"tenant_id": "00000000-0000-4000-8000-00000000dead", "role": "OWNER"}, headers={"x-admin-key": KEY})
step("a token for a tenant that does not exist is refused", s == 404, f"http {s}")

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
s, e = call("POST", "/api/v1/tally/entry", {"text": "Paid 25000 rent to Sharma by cheque on " + ENTRY_DATE, "state_code": "29"}, owner)
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
c["tally_url"] = TALLY_URL or "http://127.0.0.1:19000"
cfg.write_text(json.dumps(c))
s, _ = call("POST", "/api/v1/tally/bridge/pair", {"code": br["pairing_code"], "host": "again"})
step("pairing code is single-use", s == 409, f"http {s}")

rc, out = bridge("selftest")
step("bridge selftest passes against " + ("REAL TallyPrime" if LIVE else "fake Tally"), rc == 0, out[-90:])
time.sleep(1)
s, led = call("GET", "/api/v1/tally/ledgers", None, owner)
step("ledger list synced up to Neon", s == 200 and {l["name"] for l in led["ledgers"]} >= ({"Cash"} if LIVE else {"Rent Paid", "Bank Account"}), f"{len(led.get('ledgers', []))} ledgers")

# ---- 4. nothing moves before approval ----------------------------------------------------------------------------
base = tally_payments()
rc, out = bridge("once")
step("bridge posts nothing before approval", rc == 0 and tally_payments() == base, f"payments={tally_payments()}")
s, _ = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": "0" * 64}, owner)
step("approving a different hash is refused", s == 409, f"http {s}")
s, ap = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, owner)
step("owner approves the exact hash", s == 200 and ap.get("status") == "APPROVED", f"http {s}")
s, _ = call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, owner)
step("second approval refused", s == 409, f"http {s}")

# ---- 5. bridge posts, cloud learns the result ------------------------------------------------------------------------
rc, out = bridge("once")
step("bridge cycle succeeded", rc == 0, out[-90:])
step("Tally received exactly the approved content" if not LIVE else "REAL Tally now holds exactly one more 25,000.00 payment",
     (tally_payments() == base + 1) if LIVE else (len(imports) == 1 and hashlib.sha256(imports[0]).hexdigest() == sha), f"payments={tally_payments()}")
s, fin = call("GET", f"/api/v1/tally/batches/{bid}", None, owner)
step("batch is POSTED with Tally's counters", s == 200 and fin["status"] == "POSTED" and fin["ack"].get("created") == 1, fin.get("status", "?"))
rc, out = bridge("once")
step("rerun does not double-post", rc == 0 and tally_payments() == base + 1, f"payments={tally_payments()}")

# ---- 6. audit + isolation + revocation ------------------------------------------------------------------------------
s, log = call("GET", "/api/v1/audit", None, owner)
acts = {x["action"] for x in log.get("events", [])}
step("audit chain valid and complete", s == 200 and log.get("valid") is True and {"TALLY_BATCH_STAGED", "TALLY_BATCH_APPROVED", "BRIDGE_PAIRED", "TALLY_BATCH_POSTED"} <= acts, f"valid={log.get('valid')}")
btok = c["bridge_token"]
step("bridge token cannot read the audit log", call("GET", "/api/v1/audit", None, btok)[0] == 403)
step("bridge token cannot approve", call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, btok)[0] == 403)
other = call("POST", "/api/v1/auth/dev-token", {"tenant_id": OTHER, "role": "OWNER"}, headers={"x-admin-key": KEY})[1]["token"]
step("second REAL tenant gets 404 for the first tenant's batch", call("GET", f"/api/v1/tally/batches/{bid}", None, other)[0] == 404)
step("second real tenant sees none of the first tenant's batches", call("GET", "/api/v1/tally/batches", None, other)[1] == {"batches": []})
step("second real tenant cannot approve the first tenant's batch", call("POST", f"/api/v1/tally/batches/{bid}/approve", {"payload_sha256": sha}, other)[0] == 404)
step("second real tenant cannot read the first tenant's ledgers or audit", call("GET", "/api/v1/tally/ledgers", None, other)[1] == {"ledgers": []} and call("GET", "/api/v1/audit", None, other)[1]["events"][0]["action"] == "TENANT_CREATED")
step("second real tenant can stage its own batch", call("POST", "/api/v1/tally/batches", {"company": "Beta Books", "drafts": [e["draft"]]}, other)[0] == 200)
s, _ = call("DELETE", f"/api/v1/tally/bridges/{br['bridge_id']}", None, owner)
step("owner revokes the bridge", s == 200, f"http {s}")
step("revoked bridge is cut off", call("GET", "/api/v1/tally/bridge/pending", None, btok)[0] == 401)

print(f"\n{sum(results)}/{len(results)} steps passed")
sys.exit(0 if all(results) else 1)
