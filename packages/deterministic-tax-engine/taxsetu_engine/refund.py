"""Six income-tax refund pathways (report s8.2). Pure date logic, no LLM."""
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class RefundAdvice:
    pathway: str
    itr_u_allowed: bool
    deadline: date | None
    notes: list = field(default_factory=list)


def pick_refund_pathway(ay_start_year: int, today: date, return_filed: bool = False, audit_case: bool = False,
                        cpc_reduced_refund: bool = False, credit_failed: bool = False,
                        tds_in_other_persons_hands: bool = False, no_return_special_claim: bool = False) -> RefundAdvice:
    """ay_start_year: 2026 means AY 2026-27 (income of FY 2025-26). ITR-U can never claim/increase a refund."""
    if credit_failed:
        return RefundAdvice("REISSUE", False, None, ["Pre-validate bank account, then Services > Refund Reissue."])
    if cpc_reduced_refund:
        return RefundAdvice("SEC_154", False, None, ["Rectification u/s 154 / Tax Credit Mismatch correction."])
    if tds_in_other_persons_hands:
        return RefundAdvice("FORM_30", False, None, ["Rule 37BA declaration / Schedule TDS to transfer credit (s.199)."])
    if no_return_special_claim:
        return RefundAdvice("FORM_30", False, None, ["Claim u/s 237 read with Rule 41 (Form 30)."])
    due = date(ay_start_year, 10, 31) if audit_case else date(ay_start_year, 7, 31)
    belated = date(ay_start_year, 12, 31)
    condone_until = date(ay_start_year + 6, 3, 31)  # 5 years from end of the AY (31 Mar of ay_start_year+1)
    if today <= due and not return_filed:
        return RefundAdvice("SEC_139_1", False, due, ["e-Verify within 30 days; interest u/s 244A from 1 April."])
    if today <= belated:
        if return_filed:
            return RefundAdvice("SEC_139_5", False, belated, ["Revised return to add missed TDS/deductions."])
        return RefundAdvice("SEC_139_4", False, belated,
                            ["Belated return; fee u/s 234F; refund interest runs from filing date."])
    if today <= condone_until:
        return RefundAdvice("SEC_119_2B", False, condone_until, [
            "ITR-U (139(8A)) cannot claim or increase a refund.",
            "File condonation u/s 119(2)(b); once approved file the return under 139(9A)."])
    return RefundAdvice("NONE", False, None, ["Beyond 5-year condonation window; seek professional advice."])
