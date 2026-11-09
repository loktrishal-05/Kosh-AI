"""Smoke test of the single-entry books against a deployed API (Vercel + Neon): a simulated shop's full-year cash book is saved, corrected,
converted, closed, rolled into the next year and staged for Tally, and the converted profit is compared with the TRUE profit that only the
simulator knows. Usage: E2E_ADMIN_KEY=... [TAXSETU_API=https://taxsetu-ai.vercel.app] [SEED=7] python scripts/books_e2e.py"""
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal as D
from pathlib import Path

API = os.environ.get("TAXSETU_API", "https://taxsetu-ai.vercel.app").rstrip("/")
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
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:200].decode(errors="replace")}


spec = importlib.util.spec_from_file_location("sim", Path(__file__).resolve().parent / "single_entry_sim.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
book, truth = sim.simulate(int(os.environ.get("SEED", "7")))

adm = {"x-admin-key": KEY}
stamp = time.strftime("%H%M%S")
mk = lambda n: call("POST", "/api/v1/auth/tenants", {"legal_name": f"{n} {stamp}"}, headers=adm)[1]["tenant_id"]
A, B = mk("Books Alpha"), mk("Books Beta")
tok = lambda t, role="OWNER": call("POST", "/api/v1/auth/dev-token", {"tenant_id": t, "role": role}, headers=adm)[1]["token"]
own, other = tok(A), tok(B)

s, b = call("POST", "/api/v1/books", {k: book[k] for k in ("name", "entity_type", "period_start", "period_end", "opening", "closing")}, own)
step("book created in Neon", s == 200 and b.get("status") == "OPEN", f"http {s}")
s, added = call("POST", f"/api/v1/books/{b['book_id']}/entries", {"entries": book["entries"]}, own)
step(f"{len(book['entries'])} cash-book lines saved", s == 200 and added.get("added") == len(book["entries"]), f"http {s} {added.get('detail', '')}")

s, rep = call("GET", f"/api/v1/books/{b['book_id']}/report", None, own)
r = rep["report"]
m = lambda x: D(x)
step("converted net profit equals the simulator's TRUE profit", m(r["statements"]["profit_loss"]["net_profit"]) == truth["net_profit"], f"{r['statements']['profit_loss']['net_profit']} vs {truth['net_profit']}")
step("net sales and purchases (incl. credit ones never in the cash book) match the truth",
     m(r["statements"]["trading"]["net_sales"]) == truth["sales"] and m(r["statements"]["trading"]["net_purchases"]) == truth["purchases"])
step("balance sheet balances and total assets match the truth", r["statements"]["balance_sheet"]["balanced"] and m(r["statements"]["balance_sheet"]["total_assets"]) == truth["total_assets"])
step("trial balance balances and the independent cross-check agrees", r["trial_balance"]["balanced"] and r["crosscheck"]["agrees"])

# a correction: add a wrong line, void it with a reason, the profit returns to the truth
s, bad = call("POST", f"/api/v1/books/{b['book_id']}/entries", {"entries": [{"date": "2026-11-01", "description": "Shop rent paid", "payment": "9999", "mode": "bank"}]}, own)
wrong = m(call("GET", f"/api/v1/books/{b['book_id']}/report", None, own)[1]["report"]["statements"]["profit_loss"]["net_profit"])
step("a wrong line changes the profit", wrong == truth["net_profit"] - 9999, str(wrong))
s, _ = call("POST", f"/api/v1/books/{b['book_id']}/entries/{bad['entries'][0]['entry_id']}/void", {"reason": "typed by mistake"}, own)
fixed = m(call("GET", f"/api/v1/books/{b['book_id']}/report", None, own)[1]["report"]["statements"]["profit_loss"]["net_profit"])
step("voiding it restores the true profit; the line stays on record", s == 200 and fixed == truth["net_profit"] and
     any(e["status"] == "VOID" for e in call("GET", f"/api/v1/books/{b['book_id']}/entries?include_void=true", None, own)[1]["entries"]))

# isolation between two real tenants
step("another tenant cannot see the book", call("GET", f"/api/v1/books/{b['book_id']}", None, other)[0] == 404 and call("GET", "/api/v1/books", None, other)[1] == {"books": []})
step("another tenant cannot add to or void in it", call("POST", f"/api/v1/books/{b['book_id']}/entries", {"entries": [{"date": "2026-05-01", "description": "x", "receipt": "1"}]}, other)[0] == 404)
step("staff can enter lines but cannot close", call("POST", f"/api/v1/books/{b['book_id']}/close", {}, tok(A, "EMPLOYEE"))[0] == 403)

# Tally staging (nothing is sent: it waits for approval in the Tally Assistant)
s, t = call("POST", f"/api/v1/books/{b['book_id']}/tally", {"company": "Simulated Kirana"}, own)
step("books staged for Tally approval (masters + vouchers)", s == 200 and len(t["staged"]) >= 2 and all(x["status"] == "PENDING_APPROVAL" for x in t["staged"]), f"http {s} {len(t.get('staged', []))} batches")

# close, freeze, roll over
s, c = call("POST", f"/api/v1/books/{b['book_id']}/close", {}, own)
step("period closed with a stored snapshot", s == 200 and c.get("status") == "CLOSED", f"http {s} {c.get('detail', '')}")
step("a closed period accepts no new lines", call("POST", f"/api/v1/books/{b['book_id']}/entries", {"entries": [{"date": "2026-05-01", "description": "late", "receipt": "1"}]}, own)[0] == 409)
s, nxt = call("POST", f"/api/v1/books/{b['book_id']}/rollover", {}, own)
step("next period created with opening balances carried over", s == 200 and nxt.get("period_start") == "2027-04-01", f"http {s}")
s, nrep = call("GET", f"/api/v1/books/{nxt['book_id']}/report", None, own)
step("next year's opening capital equals last year's closing capital", m(nrep["report"]["statements"]["balance_sheet"]["capital"]["opening"]) == truth["capital"], nrep["report"]["statements"]["balance_sheet"]["capital"]["opening"])
log = call("GET", "/api/v1/audit", None, own)[1]
step("audit chain valid and records the book's life", log.get("valid") is True and {"BOOK_CREATED", "BOOK_ENTRIES_ADDED", "BOOK_ENTRY_VOIDED", "BOOK_TALLY_STAGED", "BOOK_CLOSED", "BOOK_ROLLED_OVER"} <= {e["action"] for e in log["events"]})

print(f"\n{sum(results)}/{len(results)} steps passed")
sys.exit(0 if all(results) else 1)
