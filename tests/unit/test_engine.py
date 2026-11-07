"""Deterministic engine tests. Oracles come from the report's worked examples and hand-computed slab arithmetic."""
from datetime import date, datetime
from decimal import Decimal as D

import pytest

from taxsetu_engine import ewb, gst, itr, recon, refund, tds

L, CR = 100_000, 10_000_000


# ---------------------------------------------------------------- GSTIN / PAN
def _mk(first14):
    return first14 + gst.gstin_check_char(first14)


@pytest.mark.parametrize("g", ["27AAPFU0939F1ZV", _mk("29ABCDE1234F1Z"), _mk("33AAACT2727Q1Z"), _mk("07AAAAA0000A1Z")])
def test_valid_gstin(g):
    assert gst.is_valid_gstin(g)


@pytest.mark.parametrize("g", ["", "27AAPFU0939F1ZX", "27AAPFU0939F1Z", "27aapfu0939f1zv ".replace("v", "q"),
                               "ZZAAPFU0939F1ZV", "27AAPFU0939F1AV", None])
def test_invalid_gstin(g):
    assert not gst.is_valid_gstin(g)


def test_gstin_single_char_typo_always_detected():
    base = _mk("29ABCDE1234F1Z")
    for i in range(14):
        for ch in "0123456789":
            if ch != base[i]:
                assert not gst.is_valid_gstin(base[:i] + ch + base[i + 1:])  # check-digit catches any substitution


@pytest.mark.parametrize("p,ok", [("ABCDE1234F", True), ("abcde1234f", True), ("ABCDE12345", False), ("ABCD1234F", False), ("", False)])
def test_pan(p, ok):
    assert gst.is_valid_pan(p) is ok


# ---------------------------------------------------------------- GST split
@pytest.mark.parametrize("taxable,rate,sup,pos,cg,sg,ig", [
    (100000, 18, "33", "33", "9000.00", "9000.00", "0.00"),
    (100000, 18, "33", "29", "0.00", "0.00", "18000.00"),
    (50000, 5, "27", "27", "1250.00", "1250.00", "0.00"),
    (200000, 12, "07", "09", "0.00", "0.00", "24000.00"),
    ("10.10", 5, "33", "33", "0.26", "0.25", "0.00"),
    (0, 18, "33", "33", "0.00", "0.00", "0.00"),
])
def test_split_gst(taxable, rate, sup, pos, cg, sg, ig):
    s = gst.split_gst(taxable, rate, sup, pos)
    assert (s.cgst, s.sgst, s.igst) == (D(cg), D(sg), D(ig))
    assert s.cgst + s.sgst + s.igst == s.total_tax
    assert s.invoice_total == D(str(taxable)) + s.total_tax


@pytest.mark.parametrize("hsn,desc,blocked", [
    ("8703", "", True), ("9963", "", True), ("", "Hotel Saravana restaurant bill", True), ("", "Cement 50 bags", True),
    ("7308", "MS angle", False), ("9983", "consulting", False), ("", "", False),
])
def test_blocked_17_5(hsn, desc, blocked):
    assert (gst.blocked_credit_17_5(hsn, desc) is not None) is blocked


@pytest.mark.parametrize("fwd,val,rcm", [(False, 15000, "750.00"), (True, 15000, "0.00"), (False, 0, "0.00")])
def test_gta_rcm(fwd, val, rcm):
    assert gst.gta_rcm(fwd, val) == D(rcm)


@pytest.mark.parametrize("days,nil,fee", [(10, False, "500.00"), (10, True, "200.00"), (0, False, "0.00"), (-3, False, "0.00")])
def test_late_fee(days, nil, fee):
    assert gst.late_fee_sec47(days, nil) == D(fee)


@pytest.mark.parametrize("tax,days,i", [(100000, 30, "1479.45"), (100000, 0, "0.00"), (0, 30, "0.00"), (365, 365, "65.70")])
def test_interest_sec50(tax, days, i):
    assert gst.interest_sec50(tax, days) == D(i)


@pytest.mark.parametrize("age,paid,status", [(10, False, "OK"), (149, False, "OK"), (150, False, "ALERT_150"),
                                             (170, False, "ALERT_170"), (180, False, "ALERT_170"), (181, False, "REVERSE"),
                                             (400, True, "SETTLED")])
def test_rule37_status(age, paid, status):
    from datetime import timedelta
    inv = date(2026, 1, 1)
    assert gst.rule37_status(inv, inv + timedelta(days=age), paid, 18000)["status"] == status


def test_rule37_interest_amount():
    r = gst.rule37_status(date(2026, 1, 1), date(2026, 7, 1), False, 18000)  # day 181
    assert r["reverse_itc"] == D("18000.00") and r["interest"] == D("1606.68")


# ---------------------------------------------------------------- TDS
@pytest.mark.parametrize("kw,base,tds_amt", [
    (dict(section="194C", amount=50000), "50000.00", "1000.00"),                                   # company 2%
    (dict(section="194C", amount=50000, payee_individual_or_huf=True), "50000.00", "500.00"),      # individual 1%
    (dict(section="194C", amount=20000), "0.00", "0.00"),                                          # under both limits
    (dict(section="194C", amount=20000, cumulative_before=90000), "110000.00", "2200.00"),         # crossing 1L: catch-up
    (dict(section="194C", amount=20000, cumulative_before=150000), "20000.00", "400.00"),          # already crossed
    (dict(section="194C", amount=50000, has_pan=False), "50000.00", "10000.00"),                   # no PAN 20%
    (dict(section="194C", amount=118000, gst_in_amount=18000), "100000.00", "2000.00"),            # report's Rs 1,18,000 bill
    (dict(section="194J", amount=25000), "0.00", "0.00"),
    (dict(section="194J", amount=40000), "40000.00", "4000.00"),
    (dict(section="194J", amount=40000, technical_service=True), "40000.00", "800.00"),
    (dict(section="194J", amount=20000, cumulative_before=15000), "35000.00", "3500.00"),          # crosses 30k: catch-up
    (dict(section="194H", amount=20000), "20000.00", "1000.00"),
    (dict(section="194H", amount=10000), "0.00", "0.00"),
    (dict(section="194Q", amount=2000000, cumulative_before=4000000), "1000000.00", "1000.00"),
    (dict(section="194Q", amount=1000000, cumulative_before=6000000), "1000000.00", "1000.00"),
    (dict(section="194Q", amount=1000000, cumulative_before=0), "0.00", "0.00"),
])
def test_tds(kw, base, tds_amt):
    r = tds.compute_tds(**kw)
    assert (r.base, r.tds) == (D(base), D(tds_amt))
    assert r.net_payable == D(str(kw["amount"])) - r.tds
    assert r.applicable is (D(base) > 0)


# ---------------------------------------------------------------- income tax slabs
@pytest.mark.parametrize("taxable,regime,expected", [
    (0, "NEW", 0), (400000, "NEW", 0), (1200000, "NEW", 0),            # 87A rebate zeroes tax up to 12L
    (1210000, "NEW", 10400), (1275000, "NEW", 74100), (2400000, "NEW", 312000), (3000000, "NEW", 499200),
    (250000, "OLD", 0), (500000, "OLD", 0), (1000000, "OLD", 117000), (1500000, "OLD", 273000),
    (600000, "OLD", 33800), (700000, "OLD", 54600),
])
def test_income_tax(taxable, regime, expected):
    assert itr.income_tax(taxable, regime) == D(expected)


def test_income_tax_refuses_surcharge_range():
    with pytest.raises(NotImplementedError):
        itr.income_tax(6_000_000)


def test_new_regime_never_jumps_more_than_the_income_above_12l():
    prev = itr.income_tax(1_200_000)
    for x in range(1_200_000, 1_400_000, 5_000):
        cur = itr.income_tax(x)
        assert cur >= prev                      # monotonic
        assert cur - itr.income_tax(1_200_000) <= (x - 1_200_000) * D("1.04") + 1  # marginal relief bound
        prev = cur


@pytest.mark.parametrize("gross,ded,best", [(900000, 0, "NEW"), (900000, 150000, "NEW"), (3000000, 450000, "NEW"),
                                            (1500000, 800000, "OLD")])
def test_compare_regimes(gross, ded, best):
    assert itr.compare_regimes(gross, ded)["best"] == best


# ---------------------------------------------------------------- presumptive
def test_44ad_report_example():
    p = itr.presumptive_44ad(144_00_000, 6_00_000)  # 1.5 Cr turnover, 4% cash
    assert p.eligible and p.income == D(912000) and p.limit == 3 * CR
    assert itr.income_tax(p.income - 0) == D(0)     # Rs 9.12L -> Rs 0 under 87A


def test_44ad_cash_breach_drops_limit_to_2cr():
    p = itr.presumptive_44ad(246_00_000, 14_00_000)  # 2.6 Cr, 5.38% cash
    assert not p.eligible and p.limit == 2 * CR and p.cash_ratio_pct == D("5.38")


@pytest.mark.parametrize("dig,cash,eligible", [(2_00_00_001, 0, True), (3_00_00_000, 0, True), (3_00_00_001, 0, False), (2_85_00_000, 15_00_000, True),
                                               (2_70_00_000, 30_00_000, False)])
def test_44ad_limits(dig, cash, eligible):
    assert itr.presumptive_44ad(dig, cash).eligible is eligible


@pytest.mark.parametrize("gross,cash,ok,inc", [(70 * L, 0, True, 35 * L), (80 * L, 0, False, 40 * L), (60 * L, 6 * L, False, 30 * L),
                                               (50 * L, 5 * L, True, 25 * L)])
def test_44ada(gross, cash, ok, inc):
    p = itr.presumptive_44ada(gross, cash)
    assert (p.eligible, p.income) == (ok, D(inc))


def test_44ae():
    assert itr.presumptive_44ae([(True, 16, 12), (True, 16, 12)]).income == D(384000)
    assert itr.presumptive_44ae([(False, 5, 12)]).income == D(90000)
    assert itr.presumptive_44ae([(True, 5, 12)]).income == D(144000)   # heavy deemed at least 12 tonnes
    assert not itr.presumptive_44ae([(False, 1, 12)] * 11).eligible
    assert not itr.presumptive_44ae([]).eligible


@pytest.mark.parametrize("dig,cash,alert", [(962, 38, "WARN"), (980, 20, "OK"), (946, 54, "BREACH"), (950, 50, "WARN"), (0, 0, "OK")])
def test_cash_ceiling(dig, cash, alert):
    assert itr.cash_ceiling_alert(dig, cash) == alert


def test_lock_in():
    assert itr.lock_in_44ad(2, True) and itr.lock_in_44ad(0, True) is None and itr.lock_in_44ad(2, False) is None


# ---------------------------------------------------------------- ITR router
T = itr.Taxpayer


@pytest.mark.parametrize("tp,form", [
    (T(total_income=D(800000)), "ITR-1"),
    (T(total_income=D(800000), ltcg_112a=D(100000)), "ITR-1"),
    (T(total_income=D(800000), ltcg_112a=D(150000)), "ITR-2"),
    (T(total_income=D(800000), stcg_111a=D(15000)), "ITR-2"),
    (T(total_income=D(6000000)), "ITR-2"),
    (T(total_income=D(800000), agri_income=D(6000)), "ITR-2"),
    (T(total_income=D(800000), house_properties=3), "ITR-2"),
    (T(total_income=D(800000), residency="NR"), "ITR-2"),
    (T(total_income=D(800000), director=True), "ITR-2"),
    (T(total_income=D(800000), unlisted_shares=True), "ITR-2"),
    (T(total_income=D(800000), foreign_assets=True), "ITR-2"),
    (T(total_income=D(800000), brought_forward_loss=True), "ITR-2"),
    (T(entity="HUF", total_income=D(800000)), "ITR-2"),
    (T(business_income=True, presumptive=True, total_income=D(1080000)), "ITR-4"),
    (T(business_income=True, presumptive=True, total_income=D(1080000), stcg_111a=D(15000)), "ITR-3"),   # evaluator Q7
    (T(business_income=True, presumptive=True, total_income=D(1080000), ltcg_112a=D(100000)), "ITR-4"),
    (T(business_income=True, presumptive=False, total_income=D(900000)), "ITR-3"),
    (T(business_income=True, presumptive=True, total_income=D(900000), director=True), "ITR-3"),
    (T(business_income=True, presumptive=True, total_income=D(900000), commission_income=True), "ITR-3"),
    (T(business_income=True, presumptive=True, total_income=D(900000), residency="NR"), "ITR-3"),
    (T(entity="FIRM", presumptive=True, total_income=D(900000)), "ITR-4"),
    (T(entity="FIRM", presumptive=False, total_income=D(900000)), "ITR-5"),
    (T(entity="LLP"), "ITR-5"), (T(entity="AOP"), "ITR-5"), (T(entity="BOI"), "ITR-5"),
    (T(entity="COMPANY"), "ITR-6"), (T(entity="TRUST"), "ITR-7"), (T(entity="POLITICAL"), "ITR-7"),
])
def test_route_itr(tp, form):
    got, why = itr.route_itr(tp)
    assert got == form and why


# ---------------------------------------------------------------- refund pathways
@pytest.mark.parametrize("kw,path", [
    (dict(today=date(2026, 7, 15)), "SEC_139_1"),
    (dict(today=date(2026, 7, 31)), "SEC_139_1"),
    (dict(today=date(2026, 10, 15), audit_case=True), "SEC_139_1"),
    (dict(today=date(2026, 8, 15)), "SEC_139_4"),
    (dict(today=date(2026, 12, 31)), "SEC_139_4"),
    (dict(today=date(2026, 8, 15), return_filed=True), "SEC_139_5"),
    (dict(today=date(2027, 1, 10)), "SEC_119_2B"),
    (dict(today=date(2032, 3, 31)), "SEC_119_2B"),
    (dict(today=date(2032, 4, 1)), "NONE"),
    (dict(today=date(2027, 1, 10), cpc_reduced_refund=True), "SEC_154"),
    (dict(today=date(2027, 1, 10), credit_failed=True), "REISSUE"),
    (dict(today=date(2027, 1, 10), tds_in_other_persons_hands=True), "FORM_30"),
    (dict(today=date(2027, 1, 10), no_return_special_claim=True), "FORM_30"),
])
def test_refund_pathway(kw, path):
    a = refund.pick_refund_pathway(2026, **kw)
    assert a.pathway == path and a.itr_u_allowed is False   # ITR-U can never claim a refund


# ---------------------------------------------------------------- reconciliation
def I(g, n, tx, tax, pos=""):
    return recon.Inv(g, n, D(str(tx)), D(str(tax)), pos)


G1, G2 = "29ABCDE1234F1Z5", "33AAACT2727Q1Z8"


@pytest.mark.parametrize("a,b,dist", [("kitten", "sitting", 3), ("", "abc", 3), ("abc", "abc", 0), ("INV-001", "INV001", 1), ("a", "", 1)])
def test_levenshtein(a, b, dist):
    assert recon.levenshtein(a, b) == dist


def test_reconcile_four_way():
    purchases = [I(G1, "INV-100", 1000, 180), I(G1, "000205", 2000, 360), I(G2, "B/77", 5000, 900), I(G2, "B/78", 1000, 180),
                 I(G1, "X-9", 1000, 180)]
    two_b = [I(G1, "INV100", 1000, 180),              # exact after normalisation
             I(G1, "205", 2000, 360),                 # 3 edits away -> beyond the Levenshtein<=2 tolerance
             I(G2, "B77", 5000, 800),                 # right invoice, wrong tax -> mismatch
             ]
    out = recon.reconcile(purchases, two_b)
    status = [r["status"] for r in out["rows"]]
    assert status == ["EXACT", "MISSING_2B", "MISMATCH", "MISSING_2B", "MISSING_2B"]   # "000205" vs "205" is 3 edits
    assert out["eligible_itc"] == D("180.00")
    assert out["eligible_itc"] + out["deferred_itc"] == sum((p.tax for p in purchases), D(0))


def test_reconcile_fuzzy_and_no_double_use():
    out = recon.reconcile([I(G1, "AB1234", 100, 18), I(G1, "AB1234", 100, 18)], [I(G1, "AB1243", 100, 18)])
    assert [r["status"] for r in out["rows"]] == ["FUZZY", "MISSING_2B"]   # one 2B record matches one purchase only
    assert out["eligible_itc"] == D("18.00") and out["deferred_itc"] == D("18.00")


def test_reconcile_never_matches_across_gstins():
    out = recon.reconcile([I(G1, "A1", 100, 18)], [I(G2, "A1", 100, 18)])
    assert out["rows"][0]["status"] == "MISSING_2B" and len(out["unmatched_2b"]) == 1


@pytest.mark.parametrize("sent,hrs,verdict", [(0, None, "SEND"), (1, 49, "SEND"), (1, 47.9, "WAIT"), (2, 100, "SEND"),
                                              (3, 500, "ESCALATE_CA"), (9, None, "ESCALATE_CA")])
def test_nudge_cap(sent, hrs, verdict):
    assert recon.can_nudge(sent, hrs) == verdict


# ---------------------------------------------------------------- e-Way Bill / MOV-07
@pytest.mark.parametrize("km,odc,end_day", [(0, False, 8), (100, False, 8), (200, False, 8), (201, False, 9), (250, False, 9),
                                            (400, False, 9), (401, False, 10), (20, True, 8), (25, True, 9)])
def test_ewb_validity(km, odc, end_day):
    v = ewb.ewb_valid_until(datetime(2026, 11, 7, 15, 0), km, odc)
    assert (v.day, v.hour, v.minute) == (end_day, 23, 59)


def test_ewb_windows():
    v = ewb.ewb_valid_until(datetime(2026, 11, 7, 15, 0), 250)
    assert ewb.expiry_alert_time(v).hour == 19
    lo, hi = ewb.extension_window(v)
    assert (hi - lo).total_seconds() == 16 * 3600


@pytest.mark.parametrize("val,inter,thr,req", [(50000, True, None, False), (50001, True, None, True), (80000, False, 100000, False),
                                               (120000, False, 100000, True), (60000, False, None, True)])
def test_ewb_required(val, inter, thr, req):
    assert ewb.ewb_required(val, inter, thr) is req


@pytest.mark.parametrize("decl,act,minor", [("TN01AB1234", "TN01AB1243", True), ("TN-01-AB-1234", "TN01AB1234", False),
                                            ("TN01AB1234", "TN01CD9999", False), ("TN01AB123", "TN01AB1234", False)])
def test_vehicle_typo(decl, act, minor):
    assert ewb.vehicle_typo_is_minor(decl, act) is minor


def test_mov07_report_demo_72k_to_1k():
    v = ewb.classify_mov07("VEHICLE_TYPO", True, 36000, declared="TN01AB1234", actual="TN01AB1243")
    assert v.circular_64_38_applies and v.penalty == D("1000")
    # without the typo defence the 200% demand would have been Rs 72,000
    assert ewb.classify_mov07("OTHER", True, 36000).penalty == D("72000.00")


@pytest.mark.parametrize("defect,inv,applies", [("PIN_ERROR_VALID_ADDRESS", True, True), ("HSN_DIGITS_SAME_RATE", True, True),
                                                ("VEHICLE_TYPO", False, False), ("EXPIRED_VALIDITY", True, False), ("OTHER", True, False)])
def test_mov07_gate(defect, inv, applies):
    v = ewb.classify_mov07(defect, inv, 10000, declared="TN01AB1234", actual="TN01AB1243")
    assert v.circular_64_38_applies is applies
    if not applies:
        assert v.penalty == D("20000.00")      # circular never cited when ineligible
