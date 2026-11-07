"""Smart split-pay (net base + GST escrow + TDS), supplier GST trust score, balanced multi-ledger postings, MDR unbundling."""
from dataclasses import dataclass
from decimal import Decimal

from .money import D, d, r2
from .tds import compute_tds

TRUST_FULL_PAYOUT = 800


def supplier_trust_score(months: list, active: bool = True, ewb_blocked: bool = False) -> int:
    """months: [(gstr1_on_time, gstr3b_on_time), ...] for the last 6 months. 0-900; cancelled/suspended GSTIN -> 0."""
    if not active or not months:
        return 0
    ontime = sum(int(a) + int(b) for a, b in months)
    score = int(D(900) * ontime / (2 * len(months)))
    return max(0, score - (100 if ewb_blocked else 0))


@dataclass(frozen=True)
class Split:
    base_payout: Decimal    # instant UPI/IMPS to vendor
    tds: Decimal            # withheld to the tenant's TDS challan bucket
    gst_escrow: Decimal     # held until the invoice shows in GSTR-2B
    gst_paid_direct: Decimal
    trust_score: int
    total: Decimal


def split_payment(taxable, gst, trust_score: int, tds_section: str | None = None, cumulative_before=0, **tds_kw) -> Split:
    taxable, gst = d(taxable), d(gst)
    t = compute_tds(tds_section, taxable + gst, cumulative_before, gst_in_amount=gst, **tds_kw).tds if tds_section else D("0.00")
    escrow = D("0.00") if trust_score >= TRUST_FULL_PAYOUT else r2(gst)   # compliant suppliers (>=800) are paid in full upfront
    direct = r2(gst) - escrow
    base = r2(taxable) - t + direct
    total = r2(taxable + gst)
    assert base + t + escrow == total, "split must conserve the invoice total"
    return Split(base, t, escrow, direct, trust_score, total)


def purchase_ledger_entries(taxable, gst, split: Split, blocked_17_5: bool = False) -> list:
    """Balanced double-entry lines (ledger, debit, credit) across party / purchase / credit-ledger / TDS / bank+escrow."""
    taxable, gst = r2(taxable), r2(gst)
    rows = [("Purchase (HSN nominal)", taxable + (gst if blocked_17_5 else D(0)), D(0)),
            ("Party: vendor", D(0), taxable + gst)]
    if not blocked_17_5:
        led = "Electronic Credit Ledger - ITC deferred (escrowed)" if split.gst_escrow > 0 else "Electronic Credit Ledger - ITC"
        rows.insert(1, (led, gst, D(0)))
    rows += [("Party: vendor", split.total, D(0)), ("Bank/UPI cash-book", D(0), split.base_payout)]
    if split.tds:
        rows.append(("TDS payable", D(0), split.tds))
    if split.gst_escrow:
        rows.append(("GST escrow (virtual account)", D(0), split.gst_escrow))
    assert sum(r[1] for r in rows) == sum(r[2] for r in rows), "ledger must balance"
    return rows


def unbundle_settlement(gross, mdr, gst_on_mdr, tcs_sec52, tds_194o) -> dict:
    """Marketplace/aggregator net settlement -> compound voucher. bank = gross - all deductions."""
    g, ded = r2(gross), [r2(mdr), r2(gst_on_mdr), r2(tcs_sec52), r2(tds_194o)]
    bank = g - sum(ded)
    return {"gross_sales": g, "bank": bank, "mdr_expense": ded[0], "input_gst_on_mdr": ded[1],
            "tcs_gstr8": ded[2], "tds_194o": ded[3]}
