from decimal import Decimal

import pytest

from taxsetu_engine.tally_bank import dedupe, parse_statement_csv, summary, to_drafts
from taxsetu_engine.tally_classify import learn_alias
from taxsetu_engine.tally_models import BookContext


@pytest.mark.parametrize("text", [
    '\ufeffSynthetic Bank\nAccount statement\nDate,Description,Debit,Credit,Balance,Chq/Ref\n10/04/2026,"RENT, APRIL",1000,,9000,CH123\nTotals,,1000,0\n',
    'Date,Narration,Amount,Balance\n10-04-26,"RENT, APRIL",-1000,9000\n',
    'Date,Particulars,Amount,Dr/Cr\n10-Apr-2026,"RENT, APRIL",1000,Dr\n',
])
def test_layouts(text):
    result = parse_statement_csv(text)
    assert result["errors"] == []
    assert len(result["txns"]) == 1
    txn = result["txns"][0]
    assert txn.debit == 1000 and txn.credit == 0 and txn.narration == "RENT, APRIL"
    drafts = to_drafts(result["txns"], BookContext(bank_ledger="Demo Bank"))
    assert drafts[0].balanced() and drafts[0].lines[1].ledger == "Demo Bank"
    assert drafts[0].lines[0].ledger == "Rent Paid"
    assert dedupe(result["txns"], {txn.key}) == []
    assert len(dedupe(result["txns"] * 2, set())) == 1


def test_amount_variants_errors_and_hash():
    result = parse_statement_csv('Date,Description,Amount\n2026-04-10,Unknown,"(1,200.50)"\n2026-04-11,Interest credit,25 Cr\n2026-04-12,BANK CHARGES,10 Dr\n2026-04-13,Invalid,NaN\n2026-04-14,Blank,\n31/02/2026,Invalid,5\n')
    assert len(result["txns"]) == 3 and len(result["errors"]) == 3
    assert result["txns"][0].debit == Decimal("1200.50")
    assert len(result["txns"][0].key) == 64
    assert result["txns"] == parse_statement_csv('Date,Description,Amount\n2026-04-10,Unknown,-1200.50\n2026-04-11,Interest credit,25\n2026-04-12,BANK CHARGES,-10\n')["txns"]
    assert parse_statement_csv("nonsense")["errors"]


def test_rules_alias_unknown_and_summary():
    text = ('Date,Narration,Debit,Credit\n'
            '10/04/2026,UPI/123456789012/PAYMENT FROM SHARMA TRADERS/okhdfcbank,100,,\n'
            '10/04/2026,UPI/123456789013/UNKNOWN PAYEE/okhdfcbank,200,,\n'
            '10/04/2026,ATM CASH WDL,300,,\n'
            '10/04/2026,CASH DEPOSIT,,400\n'
            '10/04/2026,EMI LOAN,500,,\n'
            '10/04/2026,INTEREST CREDIT,,50\n'
            '10/04/2026,SMS CHARGES,10,,\n'
            '10/04/2026,NEFT/REF123/RENT,600,,\n')
    txns = parse_statement_csv(text)["txns"]
    ctx = BookContext(cash_ledger="Petty Cash")
    learn_alias(ctx, "Sharma Traders", "Office Expenses")
    learn_alias(ctx, "Rent", "Professional Fees")
    drafts = to_drafts(txns, ctx)
    assert len(drafts) == 8 and all(v.balanced() for v in drafts)
    assert drafts[0].lines[0].ledger == "Office Expenses" and drafts[0].confidence == Decimal("0.95")
    assert drafts[0].reference == "123456789012"
    assert drafts[1].lines[0].ledger == "Suspense A/c" and "NEEDS_REVIEW" in drafts[1].flags
    assert drafts[1].confidence <= Decimal("0.4")
    assert [v.vtype for v in drafts[2:4]] == ["Contra", "Contra"]
    assert drafts[2].lines[0].ledger == "Petty Cash"
    assert drafts[4].lines[0].ledger == "Interest Paid" and "NEEDS_REVIEW" in drafts[4].flags
    assert drafts[5].lines[0].ledger == "Interest Received"
    assert drafts[6].lines[0].ledger == "Bank Charges"
    assert drafts[7].lines[0].ledger == "Professional Fees"
    assert all(v.source == "bank_csv" for v in drafts)
    assert summary(drafts) == {"count": 8, "auto_ready": 6, "needs_review": 2, "total_in": Decimal(450), "total_out": Decimal(1710)}


def test_money_in_under_an_expense_keyword_needs_a_human():
    from datetime import date
    from decimal import Decimal
    from taxsetu_engine.tally_bank import to_drafts
    from taxsetu_engine.tally_models import BankTxn, BookContext
    d, = to_drafts([BankTxn(date(2026, 4, 1), "UPI/123456789012/RENT APR/okaxis", credit=Decimal("20000"))], BookContext())
    assert d.vtype == "Receipt" and "NEEDS_REVIEW" in d.flags and d.confidence < Decimal("0.8")
    out, = to_drafts([BankTxn(date(2026, 4, 1), "NEFT RENT APR", debit=Decimal("20000"))], BookContext())
    assert out.vtype == "Payment" and "NEEDS_REVIEW" not in out.flags and out.lines[0].ledger == "Rent Paid"
