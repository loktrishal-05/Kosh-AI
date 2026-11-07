"""ITR-1..7 router, 44AD/44ADA/44AE presumptive income, slab tax with 87A, Old-vs-New regime."""
from dataclasses import dataclass
from decimal import Decimal

from .money import D, d, r0

L = D("100000")
CR = D("10000000")

# --- tax slabs (AY 2026-27 / FY 2025-26) -------------------------------------------------------------------
# ponytail: surcharge (>50L) not modelled; calls above that raise instead of returning a silently wrong figure.
NEW_SLABS = [(4 * L, D(0)), (8 * L, D(5)), (12 * L, D(10)), (16 * L, D(15)), (20 * L, D(20)), (24 * L, D(25)), (None, D(30))]
OLD_SLABS = [(D("250000"), D(0)), (5 * L, D(5)), (10 * L, D(20)), (None, D(30))]
STD_DED = {"NEW": D("75000"), "OLD": D("50000")}
CESS = D("0.04")


def _slab_tax(income: Decimal, slabs) -> Decimal:
    tax, lo = D(0), D(0)
    for hi, rate in slabs:
        top = income if hi is None else min(income, hi)
        if top > lo:
            tax += (top - lo) * rate / 100
        if hi is None or income <= hi:
            break
        lo = hi
    return tax


def income_tax(taxable, regime: str = "NEW") -> Decimal:
    """Tax incl. 87A rebate (+ marginal relief in new regime) and 4% cess, on taxable income after deductions."""
    inc = d(taxable)
    if inc > 50 * L:
        raise NotImplementedError("surcharge not modelled for income above Rs 50 lakh")
    if regime == "NEW":
        tax = _slab_tax(inc, NEW_SLABS)
        if inc <= 12 * L:
            tax = max(D(0), tax - min(tax, D("60000")))
        else:
            tax = min(tax, inc - 12 * L)  # marginal relief just above the rebate ceiling
    else:
        tax = _slab_tax(inc, OLD_SLABS)
        if inc <= 5 * L:
            tax = max(D(0), tax - min(tax, D("12500")))
    return r0(tax * (1 + CESS))


def compare_regimes(gross_income, old_deductions=0, salaried: bool = True) -> dict:
    g = d(gross_income)
    new_t = max(D(0), g - (STD_DED["NEW"] if salaried else 0))
    old_t = max(D(0), g - (STD_DED["OLD"] if salaried else 0) - d(old_deductions))
    tn, to = income_tax(new_t, "NEW"), income_tax(old_t, "OLD")
    return {"new_tax": tn, "old_tax": to, "best": "NEW" if tn <= to else "OLD", "saving": abs(tn - to)}


# --- presumptive taxation -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Presumptive:
    eligible: bool
    income: Decimal
    limit: Decimal
    cash_ratio_pct: Decimal
    reason: str = ""


def cash_ratio_pct(digital, cash) -> Decimal:
    t = d(digital) + d(cash)
    return D(0) if t == 0 else (d(cash) / t * 100).quantize(D("0.01"))


def presumptive_44ad(digital_turnover, cash_turnover) -> Presumptive:
    dg, ca = d(digital_turnover), d(cash_turnover)
    ratio, tot = cash_ratio_pct(dg, ca), dg + ca
    limit = 3 * CR if ratio <= 5 else 2 * CR
    ok = tot <= limit
    return Presumptive(ok, r0(dg * D("0.06") + ca * D("0.08")), limit, ratio,
                       "" if ok else f"turnover above Rs {limit:,} limit (cash {ratio}%)")


def presumptive_44ada(gross_receipts, cash_receipts=0) -> Presumptive:
    g = d(gross_receipts)
    ratio = cash_ratio_pct(g - d(cash_receipts), cash_receipts)
    limit = 75 * L if ratio <= 5 else 50 * L
    ok = g <= limit
    return Presumptive(ok, r0(g / 2), limit, ratio, "" if ok else f"receipts above Rs {limit:,} limit")


def presumptive_44ae(vehicles) -> Presumptive:
    """vehicles: iterable of (heavy: bool, gvw_tonnes, months_owned). Max 10 goods carriages."""
    vs = list(vehicles)
    inc = D(0)
    for heavy, gvw, months in vs:
        inc += D(1000) * max(d(gvw), D(12)) * months if heavy else D(7500) * months
    ok = 0 < len(vs) <= 10
    return Presumptive(ok, r0(inc), D(0), D(0), "" if ok else "44AE needs 1-10 goods carriages")


def cash_ceiling_alert(digital, cash) -> str:
    r = cash_ratio_pct(digital, cash)
    return "BREACH" if r > 5 else "WARN" if r >= D("3.8") else "OK"


def lock_in_44ad(opted_in_years: int, declared_below_floor: bool) -> str | None:
    """Sec 44AD(4)/(5): opting out after opting in bars presumptive for 5 AYs (audit u/s 44AB if above exemption)."""
    if opted_in_years > 0 and declared_below_floor:
        return "Opting out of 44AD forfeits presumptive scheme for the next 5 AYs; books (44AA) + audit (44AB) may apply."
    return None


# --- ITR form router ----------------------------------------------------------------------------------------
@dataclass
class Taxpayer:
    entity: str = "INDIVIDUAL"  # INDIVIDUAL|HUF|FIRM|LLP|AOP|BOI|COMPANY|TRUST|POLITICAL
    residency: str = "ROR"      # ROR|RNOR|NR
    total_income: Decimal = D(0)
    business_income: bool = False
    presumptive: bool = False   # business income computed under 44AD/ADA/AE
    commission_income: bool = False
    stcg_111a: Decimal = D(0)
    other_capital_gains: Decimal = D(0)  # anything other than 112A / 111A
    ltcg_112a: Decimal = D(0)
    brought_forward_loss: bool = False
    agri_income: Decimal = D(0)
    house_properties: int = 0
    director: bool = False
    unlisted_shares: bool = False
    foreign_assets: bool = False
    esop_deferred_tax: bool = False


def route_itr(t: Taxpayer) -> tuple[str, list]:
    e = t.entity
    if e in ("TRUST", "POLITICAL"):
        return "ITR-7", ["charitable/political entity (139(4A)-(4D))"]
    if e == "COMPANY":
        return "ITR-6", ["company"]
    if e in ("LLP", "AOP", "BOI"):
        return "ITR-5", [f"{e} files ITR-5"]
    cg_ok = (t.stcg_111a == 0 and t.other_capital_gains == 0 and t.ltcg_112a <= D("125000")
             and not t.brought_forward_loss)
    blockers = []
    if t.total_income > 50 * L: blockers.append("income above Rs 50 lakh")
    if t.residency != "ROR": blockers.append("not resident & ordinarily resident")
    if t.director: blockers.append("director in a company")
    if t.unlisted_shares: blockers.append("holds unlisted equity shares")
    if t.foreign_assets: blockers.append("foreign assets/income")
    if not cg_ok: blockers.append("capital gains beyond 112A <= Rs 1.25L / carried-forward loss")
    if t.agri_income > 5000: blockers.append("agricultural income above Rs 5,000")
    if t.house_properties > 2: blockers.append("more than two house properties")
    if t.esop_deferred_tax: blockers.append("deferred ESOP tax")

    if e == "FIRM":  # non-LLP partnership
        if t.presumptive and not blockers and not t.commission_income:
            return "ITR-4", ["firm with presumptive income"]
        return "ITR-5", ["firm not eligible for ITR-4"] + blockers
    # INDIVIDUAL / HUF
    if t.business_income:
        if t.presumptive and not blockers and not t.commission_income:
            return "ITR-4", ["presumptive business income within ITR-4 limits"]
        why = blockers + (["commission/brokerage income"] if t.commission_income else []) \
            + ([] if t.presumptive else ["business income not presumptive"])
        return "ITR-3", why  # 44AD stays available inside ITR-3, so no defective-return risk
    if e == "INDIVIDUAL" and not blockers:
        return "ITR-1", ["simple resident individual"]
    return "ITR-2", blockers or ["HUF without business income"]
