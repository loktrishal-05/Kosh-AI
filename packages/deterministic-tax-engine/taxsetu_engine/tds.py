"""TDS trigger engine for 194C / 194J / 194H / 194Q. Rates/thresholds live in one table so a CA can edit them."""
from dataclasses import dataclass
from decimal import Decimal

from .money import D, d, r2

# ponytail: values are the report's; Finance Act changes (e.g. 194H) must be re-verified by a CA before real use.
RULES = {
    "194C": dict(single=D("30000"), aggregate=D("100000"), rate=D("2"), rate_indiv=D("1")),
    "194J": dict(single=D("30000"), aggregate=D("30000"), rate=D("10"), rate_tech=D("2")),
    "194H": dict(single=D("15000"), aggregate=D("15000"), rate=D("5")),
    "194Q": dict(single=D("5000000"), aggregate=D("5000000"), rate=D("0.1")),
}
NO_PAN_RATE = D("20")


@dataclass(frozen=True)
class TdsResult:
    section: str
    applicable: bool
    base: Decimal
    rate_pct: Decimal
    tds: Decimal
    net_payable: Decimal


def compute_tds(section: str, amount, cumulative_before=0, payee_individual_or_huf: bool = False,
                technical_service: bool = False, has_pan: bool = True, gst_in_amount=0,
                deducted_base_before=None) -> TdsResult:
    """TDS on one payment. GST shown separately on the invoice is excluded from the base (CBDT Circular 23/2017).

    Trigger: cumulative (incl. this payment) crosses the aggregate limit -> catch-up on everything not yet deducted;
    else a single payment over the single limit (194C only differs) -> that payment alone.
    """
    rule = RULES[section]
    pay, before = d(amount) - d(gst_in_amount), d(cumulative_before)
    after = before + pay
    zero = Decimal(0)

    rate = rule["rate"]
    if section == "194C" and payee_individual_or_huf:
        rate = rule["rate_indiv"]
    if section == "194J" and technical_service:
        rate = rule["rate_tech"]
    if not has_pan:
        rate = max(rate, NO_PAN_RATE)

    lim = rule["aggregate"]
    if section == "194Q":  # only the excess over the limit is subject to TDS
        base = max(zero, after - lim) - max(zero, before - lim)
    else:
        done = d(deducted_base_before) if deducted_base_before is not None else (before if before > lim else zero)
        if after > lim:
            base = after - done
        elif pay > rule["single"]:
            base = pay
        else:
            base = zero
    base = max(base, zero)
    tds = r2(base * rate / 100)
    return TdsResult(section, base > 0, r2(base), rate, tds, r2(d(amount) - tds))
