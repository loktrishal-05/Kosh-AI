from copy import deepcopy
from decimal import Decimal, localcontext

import pytest

from taxsetu_engine.spice import draft_eaoa, draft_emoa, sample_spice


@pytest.mark.parametrize("variant,valid", [("two_subs", True), ("opc", True), ("bad_capital", False)])
@pytest.mark.parametrize("draft", [draft_emoa, draft_eaoa])
def test_samples(variant, valid, draft):
    inp = sample_spice(variant)
    original = deepcopy(inp)
    out = draft(inp)
    assert (not out["errors"]) is valid, out
    assert out["status"] == "DRAFT" and "practising CA/CS" in out["disclaimer"]
    assert inp == original


def test_capital_and_subscription_values():
    inp = sample_spice()
    inp.update(authorised_capital="2000", face_value="10.00")
    out = draft_emoa(inp)
    assert not out["errors"]
    assert Decimal(out["total_subscribed"]) == Decimal("2000")
    assert Decimal(out["clauses"]["V"]["number_of_shares"]) == Decimal("200")
    assert all(Decimal(row["value"]) == Decimal("1000") for row in out["subscription_table"])
    assert sum(Decimal(row["percentage"]) for row in out["subscription_table"]) == Decimal("100")
    inp["authorised_capital"] = "1999.99"
    assert any("exceeds" in e for e in draft_emoa(inp)["errors"])


def test_opc_two_subscribers_and_private_one():
    inp = sample_spice("opc")
    inp["subscribers"].append(sample_spice()["subscribers"][1])
    assert any("exactly 1" in e for e in draft_emoa(inp)["errors"])
    inp = sample_spice()
    inp["subscribers"].pop()
    assert any("at least 2" in e for e in draft_emoa(inp)["errors"])


def test_duplicate_pan():
    inp = sample_spice()
    inp["subscribers"][1]["pan"] = inp["subscribers"][0]["pan"]
    assert any("duplicate PAN" in e for e in draft_emoa(inp)["errors"])


def test_large_capital_remains_exact_with_small_caller_precision():
    inp = sample_spice("opc")
    inp.update(authorised_capital="999999999999999999.999999", face_value="999999999999999999.999999")
    inp["subscribers"][0]["shares"] = "999999999999999999"
    with localcontext() as context:
        context.prec = 6
        out = draft_emoa(inp)
    assert out["total_subscribed"] == "999999999999999998999999000000000000.000001"
    assert any("exceeds" in e for e in out["errors"])


@pytest.mark.parametrize("shares", ["0", "-1", "1.5", "NaN", "Infinity", None, {}, True])
def test_invalid_shares(shares):
    inp = sample_spice()
    inp["subscribers"][0]["shares"] = shares
    assert draft_emoa(inp)["errors"]


@pytest.mark.parametrize("field,value", [("proposed_names", []), ("proposed_names", [None]),
    ("proposed_names", ["Demo Limited"]), ("registered_office_state", ""), ("main_objects", [None]),
    ("authorised_capital", "NaN"), ("face_value", "0"), ("subscribers", [None]),
    ("face_value", "1e99999"), ("subscribers", "garbage")])
def test_invalid_inputs(field, value):
    inp = sample_spice()
    inp[field] = value
    assert draft_emoa(inp)["errors"]


@pytest.mark.parametrize("inp", [None, [], "garbage", {}])
@pytest.mark.parametrize("draft", [draft_emoa, draft_eaoa])
def test_garbage(inp, draft):
    assert draft(inp)["errors"]


def test_blank_entrenchment_and_opc_warning():
    inp = sample_spice("opc")
    inp["entrenched_articles"][0]["condition"] = "  "
    out = draft_eaoa(inp)
    assert any("Blank" in w for w in out["warnings"])
    assert any("one subscriber" in w for w in out["warnings"])
    assert any("all members" in w and "special resolution" in w for w in out["warnings"])
    assert out["cs_confirmation_required"]
    assert out["entrenchment_schedule"][0]["attachment"] == "INC-34"
    assert "Table F" in out["adoption"]["reference"]


def test_opc_without_entrenchment_warns():
    inp = sample_spice("opc")
    inp.pop("entrenched_articles")
    out = draft_eaoa(inp)
    assert out["warnings"] and not out["entrenchment_schedule"]


@pytest.mark.parametrize("articles", [None, "bad", [None], [{"article": []}]])
def test_bad_entrenchment(articles):
    inp = sample_spice()
    inp["entrenched_articles"] = articles
    assert draft_eaoa(inp)["errors"]
