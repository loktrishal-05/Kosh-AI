"""Verify the single-entry export against a REAL TallyPrime: convert an example, import the exported ledgers and vouchers into an EMPTY test company,
then compare every ledger's closing balance in Tally with the converter's adjusted trial balance (before closing entries, which we never export).
Usage (Tally running with its HTTP server on, an empty company open):
    python scripts/books_tally_verify.py "SE Verify Books" [business_textbook|kirana_full_year|nonprofit_club|individual_freelancer]
Education mode only accepts vouchers dated the 1st or 2nd of a month, so every date is moved to the 1st of its month (this does not change balances)."""
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "packages" / "deterministic-tax-engine")]
from taxsetu_engine import tallybooks as tb  # noqa: E402
from taxsetu_engine.single_entry import convert, to_tally  # noqa: E402

COMPANY = sys.argv[1] if len(sys.argv) > 1 else "SE Verify Books"
NAME = sys.argv[2] if len(sys.argv) > 2 else "business_textbook"
URL = os.environ.get("TALLY_URL", "http://127.0.0.1:9000")


def post(xml):
    req = urllib.request.Request(URL, data=xml.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8"})
    return urllib.request.urlopen(req, timeout=900).read().decode("utf-8", "replace")


def counters(r):
    return {k: int(v) for k, v in re.findall(r"<(CREATED|ALTERED|ERRORS|EXCEPTIONS)>(\d+)<", r)}


def tally_balances():
    x = (f"<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>TSLedgers</ID></HEADER><BODY><DESC><STATICVARIABLES>"
         f"<SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES><TDL><TDLMESSAGE>"
         '<COLLECTION NAME="TSLedgers" ISMODIFY="No"><TYPE>Ledger</TYPE><FETCH>Name, Parent, ClosingBalance</FETCH></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>')
    root = ET.fromstring(tb._drop_illegal_refs(post(x)))
    return {l.get("NAME"): D((l.findtext("CLOSINGBALANCE") or "0").strip() or "0") for l in root.iter("LEDGER") if l.get("NAME")}


book = json.loads((ROOT / "docs" / "samples" / "single_entry" / f"{NAME}.json").read_text(encoding="utf-8"))
book["entries"] = [{**e, "date": e["date"][:8] + "01"} for e in book["entries"]]          # Education mode: the 1st of the month
result = convert(book)
out = to_tally(result)
vouchers = [replace(v, date=v.date.replace(day=1) if v.date.day not in (1, 2) else v.date) for v in out["vouchers"]]
print(f"{NAME}: {len(out['ledgers'])} ledgers and {len(vouchers)} vouchers to export; engine says balanced={result['trial_balance']['balanced']}")

m = post(tb.masters_xml(COMPANY, out["ledgers"]))
pm = tb.parse_response(m)
print("masters ->", counters(m), "ok" if pm["ok"] else f"NOT OK {pm['errors']}")
bad = 0
for i in range(0, len(vouchers), 100):
    r = post(tb.voucher_xml(COMPANY, vouchers[i:i + 100], remote_id_prefix=f"ts-sev-{NAME}-{i}"))
    p = tb.parse_response(r)
    bad += 0 if p["ok"] else 1
    print(f"vouchers {i + 1}-{i + len(vouchers[i:i + 100])} ->", counters(r), "ok" if p["ok"] else f"NOT OK {p['errors']}")

tally = tally_balances()
engine = {row["ledger"]: D(row["debit"]) - D(row["credit"]) for row in result["trial_balance"]["rows"]}      # debit positive
print("\nledger                         engine (Dr+)        Tally (Dr+)       match")
mismatch = 0
for name in sorted(set(engine) | {n for n in tally if n not in ("Profit & Loss A/c",) and tally[n] != 0}):
    e, t = engine.get(name, D(0)), -tally.get(name, D(0))                      # Tally's XML shows a debit balance as negative
    ok = e == t
    mismatch += 0 if ok else 1
    print(f"{name:28} {e:>16,.2f} {t:>16,.2f}     {'OK' if ok else '<-- DIFFERENT'}")
print(f"\n{len(engine)} engine ledgers compared; mismatches: {mismatch}; failed import requests: {bad}")
sys.exit(0 if mismatch == 0 and bad == 0 else 1)
