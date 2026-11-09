"""Deterministic cash-book classification. Text is data, never instructions."""
import re

from .tally_classify import HEADS

ASSETS = {"cash": "Cash", "bank": "Bank", "debtors": "Debtors", "stock": "Stock-in-Trade",
          "fixed_assets": "Fixed Assets", "investments": "Investments",
          "prepaid_expenses": "Prepaid Expenses", "accrued_income": "Accrued Income"}
LIABILITIES = {"creditors": "Creditors", "loans": "Loans", "outstanding_expenses": "Outstanding Expenses",
               "advance_income": "Income Received in Advance"}
ADJUSTMENTS = ("outstanding_expenses", "prepaid_expenses", "accrued_income", "advance_income")
CAPITAL = {"business": "Capital", "individual": "Net Worth", "nonprofit": "Capital Fund"}
INCOME = {"cash_sale": "Sales", "interest_income": "Interest Received", "commission_income": "Commission Received",
          "rent_income": "Rent Received", "other_income": "Other Income", "refund": "Other Income",
          "subscription": "Subscriptions", "donation": "Donations", "grant": "Grants", "event_income": "Event Income",
          "professional_income": "Professional Income", "salary_income": "Salary Income",
          "dividend_income": "Dividend Income", "gift": "Gifts Received"}
COUNTERS = {**INCOME, "debtor_receipt": "Debtors", "creditor_payment": "Creditors", "cash_purchase": "Purchases",
            "drawings": "Drawings", "asset_purchase": "Fixed Assets", "asset_sale": "Fixed Assets",
            "loan_received": "Loans", "loan_repayment": "Loans", "loan_principal": "Loans",
            "loan_interest": "Interest Paid", "loan_emi": "Interest Paid", "investment": "Investments"}
COMMON_RECEIPTS = (("loan_received", r"loan|borrowed"), ("asset_sale", r"sale of old|sold.*(?:furniture|computer|vehicle|machinery|scrap)"),
                   ("interest_income", r"interest"), ("commission_income", r"commission"), ("rent_income", r"rent"))
RECEIPTS = {
    "business": (("capital_introduced", r"capital|invested by owner|introduced"),
                 ("debtor_receipt", r"debtors?|against bills?|against invoice|customer dues|outstanding"),
                 *COMMON_RECEIPTS, ("other_income", r"refund|misc income"), ("cash_sale", r"cash sales?|sales?")),
    "nonprofit": (("corpus_donation", r"corpus|building fund|endowment|life membership"),
                  ("subscription", r"subscription|membership fee"), ("donation", r"donation"), ("grant", r"grant"),
                  *COMMON_RECEIPTS, ("event_income", r"event|sports day|fundraising"), ("other_income", r"refund|misc income")),
    "individual": (("professional_income", r"freelance|client|consulting|professional"), ("salary_income", r"salary"),
                   *COMMON_RECEIPTS, ("dividend_income", r"dividend"), ("gift", r"gift"),
                   ("refund", r"refund"), ("other_income", r"misc income")),
}
EXPENSES = ((r"transport|freight|carriage|cartage", "Transport and Freight"),
            (r"advertisement|advertising", "Advertisement"), (r"wages|salaries|salary|staff", "Salary and Wages"), *HEADS)
PERSONAL = ((r"groceries|household|vegetables|supermarket", "Groceries and Household"), (r"rent", "Rent"),
            (r"electricity|water|gas|mobile|broadband|bills|utilities", "Utilities"),
            (r"fuel|petrol|cab|taxi|bus|metro|transport", "Transport"), (r"medical|medicine|hospital", "Medical"),
            (r"school fees|tuition|course|education", "Education"), (r"insurance|premium", "Insurance"),
            (r"donation|charity", "Donations Given"), (r"movies|dining|restaurant|holiday|entertainment", "Entertainment"),
            (r"tax", "Taxes Paid"), (r"interest", "Interest Paid"))
CONTRA = r"deposited into bank|cash deposited|withdrawn from bank|atm|cash withdrawal|transfer to bank"
ASSET_PURCHASE = r"purchase of.*(?:furniture|computer|laptop|machine|machinery|vehicle|scooter|truck|equipment|fittings|printer|\bac\b)"
RESERVED = set(ASSETS.values()) | set(LIABILITIES.values()) | set(CAPITAL.values()) | {
    "Drawings", "Trading A/c", "Profit & Loss A/c", "Income & Expenditure A/c", "Sales", "Purchases",
    "Sales Returns", "Purchase Returns"}


def valid_head(head):
    return isinstance(head, str) and bool(head.strip()) and len(head) <= 99 and head not in RESERVED and not any(ord(c) < 32 for c in head)


def classify(entry, entity, incoming):
    """Return category, counter ledger, confidence and review reason."""
    hint = str(entry.get("hint") or "")
    allowed = {key for key, _ in RECEIPTS[entity]} | {"contra"} if incoming else {
        "asset_purchase", "loan_repayment", "contra", "investment", "loan_principal", "loan_interest", "loan_emi"}
    if not incoming and entity == "business":
        allowed |= {"creditor_payment", "cash_purchase", "drawings"}
    if hint.startswith("expense:") and not incoming and valid_head(hint[8:]):
        return hint, hint[8:], 1, ""
    text = str(entry.get("description") or "") + " " + str(entry.get("party") or "")
    def matches(pattern):
        return re.search(r"\b(?:" + pattern + r")s?\b", text, re.I)
    category = hint if hint in allowed else ""
    if not category and matches(CONTRA):
        category = "contra"
    if not category and incoming:
        category = next((key for key, pattern in RECEIPTS[entity] if matches(pattern)), "")
    if not category and not incoming:
        if matches(ASSET_PURCHASE):
            category = "asset_purchase"
        elif matches(r"loan repaid|repayment of loan"):
            category = "loan_repayment"
        elif entity == "individual":
            category = next((key for key, pattern in (("loan_principal", r"principal"), ("loan_interest", r"interest part"),
                            ("loan_emi", r"emi"), ("investment", r"sip|mutual fund|fd|fixed deposit|ppf|shares|gold")) if matches(pattern)), "")
        elif entity == "business":
            category = next((key for key, pattern in (("creditor_payment", r"suppliers?|creditors?|against bills|dues"),
                            ("cash_purchase", r"purchase of goods|cash purchases?|goods|stock|raw material"),
                            ("drawings", r"owner|household|personal|home|drawings|withdrawn by")) if matches(pattern)), "")
    if category:
        ledger = CAPITAL[entity] if category in {"capital_introduced", "corpus_donation"} else COUNTERS.get(category, "")
        reason = "What is the principal/interest split of this EMI?" if category == "loan_emi" else ""
        if incoming and hint not in allowed and category != "contra":
            candidates = {key for key, pattern in RECEIPTS[entity] if matches(pattern)}
            if "asset_sale" in candidates:
                candidates.discard("cash_sale")
            if "corpus_donation" in candidates:
                candidates -= {"donation", "subscription"}
            if len(candidates) > 1:
                reason = "Which income or capital category applies to this receipt?"
        return category, ledger, 0.7 if reason else 1 if hint in allowed else 0.9, reason
    if not incoming:
        rules = PERSONAL if entity == "individual" else EXPENSES
        if entity == "nonprofit" and matches(r"event|camp|training|relief|scholarship|sports"):
            return "expense:Program Expenses", "Program Expenses", 0.9, ""
        heads = [head for pattern, head in rules if matches(pattern)]
        if heads:
            head = "Salaries" if entity == "nonprofit" and heads[0] == "Salary and Wages" else heads[0]
            # Overlapping synonyms for the same head are not ambiguous.
            distinct = set(heads)
            return "expense:" + head, head, 0.85, "Which expense head applies?" if len(distinct) > 1 else ""
    if incoming and entity == "business" and not text.strip():
        return "cash_sale", "Sales", 0.7, ""
    ledger = "Sales" if incoming and entity == "business" else "Other Income" if incoming else "Other Expenses"
    return "cash_sale" if ledger == "Sales" else "other_income" if incoming else "expense:" + ledger, ledger, 0.7 if ledger == "Sales" else 0.4, "Please confirm the classification of this entry."
