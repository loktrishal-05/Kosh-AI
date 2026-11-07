"""GSTIN/PAN validation, CGST/SGST/IGST split, Sec 17(5) blocked credit, GTA RCM, Rules 37/47/50."""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .money import D, d, r2

_ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _ALPHA.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _ALPHA[(36 - total % 36) % 36]


def is_valid_gstin(g: str) -> bool:
    g = (g or "").strip().upper()
    return bool(_GSTIN_RE.match(g)) and gstin_check_char(g[:14]) == g[14]


def is_valid_pan(p: str) -> bool:
    return bool(_PAN_RE.match((p or "").strip().upper()))


@dataclass(frozen=True)
class GstSplit:
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total_tax: Decimal
    invoice_total: Decimal


def split_gst(taxable, rate_pct, supplier_state: str, place_of_supply: str) -> GstSplit:
    """Intra-state -> CGST+SGST (half each); inter-state -> IGST. States are 2-digit GST state codes."""
    taxable, rate = d(taxable), d(rate_pct)
    tax = r2(taxable * rate / 100)
    if supplier_state == place_of_supply:
        half = r2(tax / 2)
        cg, sg, ig = half, tax - half, D("0.00")  # sgst takes the rounding paisa so cg+sg == tax
    else:
        cg = sg = D("0.00")
        ig = tax
    return GstSplit(cg, sg, ig, tax, r2(taxable + tax))


# ponytail: prefix/keyword heuristic, replace with the full Sec 17(5) HSN table when a CA signs off the list.
_BLOCKED_PREFIX = {"8703": "motor cars", "9963": "food/accommodation", "9954": "works contract (immovable)",
                   "9971": "insurance (health/life) unless obligatory", "999722": "beauty/health services"}
_BLOCKED_WORDS = ("restaurant", "food", "catering", "hotel", "club membership", "beauty", "cement", "motor car",
                  "car repair", "life insurance", "health insurance")


def blocked_credit_17_5(hsn_sac: str = "", description: str = "") -> str | None:
    """Return the reason ITC is blocked under Sec 17(5), else None."""
    code, text = (hsn_sac or "").strip(), (description or "").lower()
    for p, why in _BLOCKED_PREFIX.items():
        if code.startswith(p):
            return why
    for w in _BLOCKED_WORDS:
        if w in text:
            return w
    return None


def gta_rcm(gta_charged_forward_12pct: bool, freight_value) -> Decimal:
    """Notification 13/2017-CT(R): if GTA did not charge 12% forward GST, recipient pays 5% RCM (claimable as ITC)."""
    return D("0.00") if gta_charged_forward_12pct else r2(d(freight_value) * D("0.05"))


def late_fee_sec47(days_late: int, nil_return: bool = False) -> Decimal:
    # ponytail: no statutory cap applied (caps vary by turnover/notification); add when a CA supplies them.
    return r2(max(days_late, 0) * (D("20") if nil_return else D("50")))


def interest_sec50(net_cash_tax, days_late: int) -> Decimal:
    return r2(d(net_cash_tax) * D("0.18") * max(days_late, 0) / 365)


def rule37_status(invoice_date: date, today: date, paid: bool, itc, availed_on: date | None = None) -> dict:
    """180-day vendor payment clock. Alerts at day 150/170; reversal + 18% interest once >180 unpaid."""
    age = (today - invoice_date).days
    if paid:
        return {"age_days": age, "status": "SETTLED", "reverse_itc": D("0.00"), "interest": D("0.00")}
    if age > 180:
        since = (today - (availed_on or invoice_date)).days
        return {"age_days": age, "status": "REVERSE", "reverse_itc": r2(itc),
                "interest": r2(d(itc) * D("0.18") * max(since, 0) / 365)}
    status = "ALERT_170" if age >= 170 else "ALERT_150" if age >= 150 else "OK"
    return {"age_days": age, "status": status, "reverse_itc": D("0.00"), "interest": D("0.00")}
