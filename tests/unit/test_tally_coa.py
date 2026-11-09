import xml.etree.ElementTree as ET

import pytest

from taxsetu_engine.tally_coa import plain_explanations, starter_pack
from taxsetu_engine.tallybooks import masters_xml


@pytest.mark.parametrize("kind", ["trader", "service", "manufacturer"])
def test_starter_pack(kind):
    pack = starter_pack(kind, "29")
    names = [l.name for l in pack]
    assert len(names) == len(set(names))
    assert all(plain_explanations().get(name) for name in names)
    duties = [l for l in pack if l.name.startswith(("Input ", "Output "))]
    assert len(duties) == 6
    for ledger in duties:
        assert ledger.parent == "Duties & Taxes"
        assert ledger.gst_duty_head == {"CGST": "Central Tax", "SGST": "State Tax", "IGST": "Integrated Tax"}[ledger.name.split()[1]]
        assert ledger.state == "29"
    assert {"Purchases", "Sales", "Bank Account", "Cash", "Round Off", "Suspense A/c"} <= set(names)
    assert {"TDS Payable - " + s for s in ("194C", "194J", "194H", "194Q", "194I")} <= set(names)
    assert ("Raw Material Purchases" in names) == (kind == "manufacturer")
    assert ("Freight Inward" in names) == (kind == "manufacturer")
    root = ET.fromstring(masters_xml("Example Company", pack))
    assert len(root.findall(".//LEDGER")) == len(pack)


def test_unknown_business():
    with pytest.raises(ValueError):
        starter_pack("unknown", "29")


def test_explanations_are_independent():
    meanings = plain_explanations()
    meanings.clear()
    assert plain_explanations()["Cash"]
