"""Report-based compliance watchdog, TDS interest, and monthly action windows."""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .money import d, r2


def consecutive_defaults(filed: list[bool]) -> int:
    count = 0
    for on_time in reversed(filed):
        if on_time:
            break
        count += 1
    return count


def ewb_block_status(consignor: dict, consignee: dict) -> dict:
    blocked_parties, reasons = [], []
    warn = False
    for party, returns in (("CONSIGNEE", consignee), ("CONSIGNOR", consignor)):
        party_blocked = False
        for key, label in (("GSTR1", "GSTR-1"), ("GSTR3B", "GSTR-3B")):
            defaults = consecutive_defaults(returns.get(key, []))
            if defaults:
                reasons.append(f"{party} {label}: {defaults} consecutive defaults")
            party_blocked |= defaults >= 2
            warn |= defaults == 1
        if party_blocked:
            blocked_parties.append(party)
    blocked = bool(blocked_parties)
    return {"blocked": blocked, "warn": warn and not blocked,
            "blocked_parties": blocked_parties, "reasons": reasons}


def tds_due_date(deducted_on: date) -> date:
    if deducted_on.month == 3:
        return date(deducted_on.year, 4, 30)
    following = deducted_on.replace(day=1) + timedelta(days=32)
    return following.replace(day=7)


def tds_interest_201_1a(tds_amount, deducted_on: date, deposited_on: date | None, today: date) -> Decimal:
    """Count monthly anniversaries, clamping the deduction day to the end month's last day."""
    amount = d(tds_amount)
    end = deposited_on if deposited_on is not None else today
    if not amount.is_finite() or amount < 0:
        raise ValueError("TDS amount must be finite and non-negative")
    if end < deducted_on:
        raise ValueError("Interest end date precedes deduction")
    if end <= tds_due_date(deducted_on):
        return r2(0)
    months = (end.year - deducted_on.year) * 12 + end.month - deducted_on.month
    anniversary_day = min(deducted_on.day, monthrange(end.year, end.month)[1])
    months += end.day > anniversary_day
    return r2(amount * d("0.015") * months)


@dataclass(frozen=True)
class Window:
    name: str
    start: date
    end: date
    due: date | None
    actions: tuple[str, ...]


def schedule(anchor: date, qrmp: bool = False) -> list[Window]:
    """Return the source report's windows for the calendar month containing anchor."""
    first = anchor.replace(day=1)
    outward_day = 13 if qrmp else 11
    # ponytail: QRMP GSTR-3B is state-dependent (22nd/24th); use the report's 20th until state scheduling is added.
    return [
        Window("Daily operations", first, first.replace(day=monthrange(first.year, first.month)[1]), None, (
            "update net GST cash-liability meter",
            "check cumulative vendor payments against 194C/194J/194H/194Q thresholds",
            "verify e-Way Bill validity windows",
            "monitor 5% cash-receipt ceiling",
        )),
        Window("TDS and payroll", first.replace(day=5), first.replace(day=7), first.replace(day=7), (
            "aggregate prior-month TDS",
            "prepare ITNS-281 challan",
            "update Labour Form A and Form B registers",
            "prompt 1-click payment before due date (avoid Section 201(1A) interest)",
        )),
        Window("Outward supplies", first.replace(day=8), first.replace(day=outward_day), first.replace(day=outward_day), (
            "audit outward invoices",
            "repair invalid GSTIN checksums and HSN mismatches",
            "reconcile e-invoice IRNs",
            "stage IFF" if qrmp else "stage GSTR-1",
        )),
        Window("Inward credit recovery", first.replace(day=14), first.replace(day=17), None, (
            "reconcile GSTR-2B on the 14th",
            "send supplier nudges",
            "stage IMS accept/pending actions",
        )),
        Window("Tax settlement", first.replace(day=18), first.replace(day=20), first.replace(day=20), (
            "compute credit-ledger vs cash-ledger offset",
            "check Rule 37 180-day reversals",
            "check Rule 86B 1% cash rule",
            "explain net payable",
            "request human OTP approval (never file automatically)",
        )),
    ]


def next_deadline(anchor: date, qrmp: bool = False) -> tuple[Window, int]:
    for window in schedule(anchor, qrmp):
        if window.due is not None and window.due >= anchor:
            return window, (window.due - anchor).days
    following = (anchor.replace(day=1) + timedelta(days=32)).replace(day=1)
    window = schedule(following, qrmp)[1]
    return window, (window.due - anchor).days
