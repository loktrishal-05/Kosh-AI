"""e-Way Bill validity (Rule 138(10)), alert timing, and MOV-07 / Circular 64/38 eligibility (FR-011, FR-012)."""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .gst import is_valid_gstin  # noqa: F401  (re-exported for callers building EWB payloads)
from .money import D, d, r2
from .recon import levenshtein


def ewb_required(consignment_value, interstate: bool, state_threshold=None) -> bool:
    """>Rs 50,000 inter-state; intra-state uses a state threshold if supplied."""
    limit = d(state_threshold) if (state_threshold is not None and not interstate) else D("50000")
    return d(consignment_value) > limit


def ewb_valid_until(generated_at: datetime, distance_km, odc: bool = False) -> datetime:
    """1 day per 200 km (20 km if ODC); each day = 24h from generation; expires at midnight ending the final day."""
    per = 20 if odc else 200
    days = max(1, math.ceil(d(distance_km) / per))
    end = generated_at + timedelta(hours=24 * days)
    return end.replace(hour=23, minute=59, second=59, microsecond=0)


def extension_window(valid_until: datetime) -> tuple:
    return valid_until - timedelta(hours=8), valid_until + timedelta(hours=8)


def expiry_alert_time(valid_until: datetime, hours_before: int = 4) -> datetime:
    return valid_until - timedelta(hours=hours_before)


@dataclass(frozen=True)
class Mov07Verdict:
    circular_64_38_applies: bool
    penalty: Decimal
    basis: str
    reason: str


def vehicle_typo_is_minor(declared: str, actual: str) -> bool:
    a, b = declared.replace(" ", "").replace("-", "").upper(), actual.replace(" ", "").replace("-", "").upper()
    return a != b and len(a) == len(b) and levenshtein(a, b) <= 2


def classify_mov07(defect: str, valid_invoice_on_file: bool, tax_payable, **kw) -> Mov07Verdict:
    """defect: VEHICLE_TYPO | PIN_ERROR_VALID_ADDRESS | HSN_DIGITS_SAME_RATE | EXPIRED_VALIDITY | OTHER.
    Circular 64/38 relief is unlocked ONLY with a valid invoice on file and a clerical defect (never a hallucinated cite).
    """
    tax = d(tax_payable)
    if not valid_invoice_on_file:
        return Mov07Verdict(False, r2(tax * 2), "s.129(1)", "no matching tax invoice - relief not available")
    if defect == "VEHICLE_TYPO" and not vehicle_typo_is_minor(kw.get("declared", ""), kw.get("actual", "")):
        return Mov07Verdict(False, r2(tax * 2), "s.129(1)", "vehicle number differs by more than 2 characters")
    if defect in ("VEHICLE_TYPO", "PIN_ERROR_VALID_ADDRESS", "HSN_DIGITS_SAME_RATE"):
        return Mov07Verdict(True, D("1000"), "s.125 (500 CGST + 500 SGST)", "minor clerical error, Circular 64/38/2018-GST")
    if defect == "EXPIRED_VALIDITY":
        return Mov07Verdict(False, r2(tax * 2), "s.129(1)",
                            "expiry is not a clerical error: file bona-fide representation with breakdown evidence")
    return Mov07Verdict(False, r2(tax * 2), "s.129(1)", "defect not covered by Circular 64/38")
