"""Planner boundaries and report oracles; all money expectations use Decimal."""
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal as D

import pytest

from taxsetu_engine import planner


@pytest.mark.parametrize("filed,expected", [
    ([], 0), ([True], 0), ([False], 1), ([True, False, False], 2),
    ([False, False, False], 3), ([False, False, True], 0),
    ([False, False, True, False], 1),
])
def test_consecutive_defaults(filed, expected):
    assert planner.consecutive_defaults(filed) == expected


@pytest.mark.parametrize("party", ["CONSIGNOR", "CONSIGNEE"])
@pytest.mark.parametrize("key,label", [("GSTR1", "GSTR-1"), ("GSTR3B", "GSTR-3B")])
@pytest.mark.parametrize("filed,count", [
    ([], 0), ([True], 0), ([False], 1), ([False, False], 2),
    ([False, False, False], 3), ([False, False, True], 0),
])
def test_ewb_boundaries(party, key, label, filed, count):
    consignor = {key: filed} if party == "CONSIGNOR" else {}
    consignee = {key: filed} if party == "CONSIGNEE" else {}
    result = planner.ewb_block_status(consignor, consignee)
    assert result == {
        "blocked": count >= 2, "warn": count == 1,
        "blocked_parties": [party] if count >= 2 else [],
        "reasons": [f"{party} {label}: {count} consecutive defaults"] if count else [],
    }


def test_ewb_both_parties_and_return_types():
    result = planner.ewb_block_status(
        {"GSTR1": [False, False], "GSTR3B": [False, False, False]},
        {"GSTR3B": [False, False]},
    )
    assert result["blocked_parties"] == ["CONSIGNEE", "CONSIGNOR"]
    assert result["blocked"] and not result["warn"]
    assert len(result["reasons"]) == 3


def test_ewb_block_suppresses_warning():
    result = planner.ewb_block_status({"GSTR1": [False]}, {"GSTR3B": [False, False]})
    assert result["blocked"] and not result["warn"]
    assert result["blocked_parties"] == ["CONSIGNEE"]


@pytest.mark.parametrize("deducted,due", [
    (date(2026, 1, 20), date(2026, 2, 7)),
    (date(2026, 3, 10), date(2026, 4, 30)),
    (date(2026, 3, 31), date(2026, 4, 30)),
    (date(2026, 12, 31), date(2027, 1, 7)),
])
def test_tds_due_date(deducted, due):
    assert planner.tds_due_date(deducted) == due


@pytest.mark.parametrize("deducted,end,expected", [
    (date(2026, 1, 20), date(2026, 2, 20), "150.00"),
    (date(2026, 1, 20), date(2026, 2, 21), "300.00"),
    (date(2026, 1, 20), date(2026, 2, 7), "0.00"),
    (date(2026, 1, 20), date(2026, 2, 6), "0.00"),
    (date(2026, 3, 10), date(2026, 4, 30), "0.00"),
    (date(2026, 3, 10), date(2026, 5, 1), "300.00"),
    (date(2026, 1, 31), date(2026, 2, 28), "150.00"),
    (date(2028, 1, 31), date(2028, 2, 29), "150.00"),
    (date(2026, 1, 31), date(2026, 3, 1), "300.00"),
    (date(2026, 1, 31), date(2026, 3, 31), "300.00"),
    (date(2026, 12, 20), date(2027, 1, 21), "300.00"),
])
@pytest.mark.parametrize("deposited", [True, False])
def test_tds_interest(deducted, end, expected, deposited):
    result = planner.tds_interest_201_1a(
        10000, deducted, end if deposited else None, date(2030, 1, 1) if deposited else end,
    )
    assert isinstance(result, D)
    assert result == D(expected)


@pytest.mark.parametrize("amount,expected", [("1", "0.02"), (D("100.50"), "1.51"), (0, "0.00")])
def test_tds_interest_rounding(amount, expected):
    assert planner.tds_interest_201_1a(amount, date(2026, 1, 20), date(2026, 2, 20), date(2026, 2, 20)) == D(expected)


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity"])
def test_tds_invalid_amount(amount):
    with pytest.raises(ValueError):
        planner.tds_interest_201_1a(amount, date(2026, 1, 20), None, date(2026, 2, 20))


def test_tds_invalid_date_order():
    with pytest.raises(ValueError):
        planner.tds_interest_201_1a(100, date(2026, 1, 20), None, date(2026, 1, 19))


@pytest.mark.parametrize("anchor,last", [
    (date(2026, 1, 25), 31), (date(2026, 2, 1), 28),
    (date(2028, 2, 29), 29), (date(2026, 4, 30), 30),
])
@pytest.mark.parametrize("qrmp", [False, True])
def test_schedule(anchor, last, qrmp):
    windows = planner.schedule(anchor, qrmp)
    assert [w.name for w in windows] == [
        "Daily operations", "TDS and payroll", "Outward supplies", "Inward credit recovery", "Tax settlement",
    ]
    assert [w.start.day for w in windows] == [1, 5, 8, 14, 18]
    assert [w.end.day for w in windows] == [last, 7, 13 if qrmp else 11, 17, 20]
    assert [w.due.day if w.due else None for w in windows] == [None, 7, 13 if qrmp else 11, None, 20]
    assert [w.start for w in windows] == sorted(w.start for w in windows)
    for window in windows:
        assert window.start <= window.end
        assert (window.start.year, window.start.month) == (anchor.year, anchor.month)
        assert (window.end.year, window.end.month) == (anchor.year, anchor.month)
        assert isinstance(window.actions, tuple) and all(window.actions)
    assert [len(w.actions) for w in windows] == [4, 4, 4, 3, 5]
    assert windows[2].actions[-1] == ("stage IFF" if qrmp else "stage GSTR-1")
    assert windows[4].actions[-1] == "request human OTP approval (never file automatically)"
    with pytest.raises(FrozenInstanceError):
        windows[0].name = "changed"


@pytest.mark.parametrize("anchor,qrmp,name,due,days", [
    (date(2026, 1, 1), False, "TDS and payroll", date(2026, 1, 7), 6),
    (date(2026, 1, 7), False, "TDS and payroll", date(2026, 1, 7), 0),
    (date(2026, 1, 8), False, "Outward supplies", date(2026, 1, 11), 3),
    (date(2026, 1, 11), False, "Outward supplies", date(2026, 1, 11), 0),
    (date(2026, 1, 12), False, "Tax settlement", date(2026, 1, 20), 8),
    (date(2026, 1, 12), True, "Outward supplies", date(2026, 1, 13), 1),
    (date(2026, 1, 13), True, "Outward supplies", date(2026, 1, 13), 0),
    (date(2026, 1, 20), False, "Tax settlement", date(2026, 1, 20), 0),
    (date(2026, 2, 28), False, "TDS and payroll", date(2026, 3, 7), 7),
    (date(2026, 12, 25), False, "TDS and payroll", date(2027, 1, 7), 13),
    (date(2026, 12, 25), True, "TDS and payroll", date(2027, 1, 7), 13),
])
def test_next_deadline(anchor, qrmp, name, due, days):
    window, remaining = planner.next_deadline(anchor, qrmp)
    assert (window.name, window.due, remaining) == (name, due, days)
    assert window in planner.schedule(due, qrmp)
