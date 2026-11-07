"""4-way GSTR-2B vs Purchase Register reconciliation (FR-007). Exact / Fuzzy / Mismatch / Missing-in-2B."""
import re
from dataclasses import dataclass
from decimal import Decimal

from .money import D, d, r2


@dataclass(frozen=True)
class Inv:
    gstin: str
    inv_no: str
    taxable: Decimal
    tax: Decimal  # total CGST+SGST+IGST
    pos: str = ""


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_inv(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _same_amounts(a: Inv, b: Inv) -> bool:
    return r2(a.taxable) == r2(b.taxable) and r2(a.tax) == r2(b.tax) and (not a.pos or not b.pos or a.pos == b.pos)


def reconcile(purchases: list, gstr2b: list, max_edit: int = 2) -> dict:
    """Each purchase is matched to at most one 2B record. Returns per-invoice status + ITC totals."""
    left = list(gstr2b)
    rows = []
    for p in purchases:
        pn, status, hit = norm_inv(p.inv_no), "MISSING_2B", None
        same_party = [g for g in left if g.gstin == p.gstin]
        for g in same_party:                       # tier 1: exact
            if norm_inv(g.inv_no) == pn and _same_amounts(p, g):
                status, hit = "EXACT", g
                break
        if hit is None:
            for g in same_party:                   # tier 3: right invoice, wrong tax/POS
                if norm_inv(g.inv_no) == pn:
                    status, hit = "MISMATCH", g
                    break
        if hit is None:
            for g in same_party:                   # tier 2: typo'd number with identical GSTIN + amounts
                if levenshtein(norm_inv(g.inv_no), pn) <= max_edit and _same_amounts(p, g):
                    status, hit = "FUZZY", g
                    break
        if hit is not None:
            left.remove(hit)
        rows.append({"invoice": p, "status": status, "matched": hit})
    eligible = sum((r["invoice"].tax for r in rows if r["status"] in ("EXACT", "FUZZY")), D(0))
    deferred = sum((r["invoice"].tax for r in rows if r["status"] in ("MISSING_2B", "MISMATCH")), D(0))
    return {"rows": rows, "eligible_itc": r2(eligible), "deferred_itc": r2(deferred), "unmatched_2b": left,
            "chase": [r["invoice"] for r in rows if r["status"] in ("MISSING_2B", "MISMATCH")]}


def can_nudge(nudges_sent: int, hours_since_last: float | None, max_nudges: int = 3, cooldown_h: int = 48) -> str:
    """Hard loop cap: max 3 nudges per invoice per period, 48h cooldown, then escalate to the CA queue."""
    if nudges_sent >= max_nudges:
        return "ESCALATE_CA"
    if hours_since_last is not None and hours_since_last < cooldown_h:
        return "WAIT"
    return "SEND"
