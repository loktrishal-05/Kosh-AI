"""Small starter charts for accounting vouchers."""
from .tally_models import LedgerSpec


_EXPENSES = {
    "Rent Paid": "Money paid to use your business premises.",
    "Salary and Wages": "Money paid to your employees for their work.",
    "Electricity Charges": "Money spent on electricity for the business.",
    "Telephone and Internet": "Money spent on business calls and internet access.",
    "Office Expenses": "Everyday costs of running your office.",
    "Bank Charges": "Fees charged by your bank.",
    "Interest Paid": "Money paid for borrowing money.",
    "Professional Fees": "Money paid to experts such as accountants and consultants.",
    "Repairs and Maintenance": "Money spent keeping your equipment and premises working.",
    "Travelling Expenses": "Money spent travelling for business.",
    "Printing and Stationery": "Money spent on printing, paper and office supplies.",
    "Insurance": "Money paid for insurance cover.",
}
_TDS = ("194C", "194J", "194H", "194Q", "194I")
_DUTIES = {"CGST": "Central Tax", "SGST": "State Tax", "IGST": "Integrated Tax"}


def starter_pack(business_type: str, state_code: str) -> list[LedgerSpec]:
    """Return the ledgers needed by the draft builders."""
    if business_type not in ("trader", "service", "manufacturer"):
        raise ValueError("unknown business type")
    ledgers = [LedgerSpec(f"{direction} {tax}", "Duties & Taxes", state=state_code, gst_duty_head=head)
               for direction in ("Input", "Output") for tax, head in _DUTIES.items()]
    ledgers += [LedgerSpec("Purchases", "Purchase Accounts"), LedgerSpec("Sales", "Sales Accounts")]
    if business_type == "manufacturer":
        ledgers += [LedgerSpec("Raw Material Purchases", "Purchase Accounts"),
                    LedgerSpec("Freight Inward", "Direct Expenses")]
    ledgers += [LedgerSpec(name, "Indirect Expenses") for name in _EXPENSES]
    ledgers += [LedgerSpec(name, "Indirect Incomes") for name in ("Interest Received", "Discount Received")]
    ledgers += [LedgerSpec("Bank Account", "Bank Accounts"), LedgerSpec("Cash", "Cash-in-Hand")]
    ledgers += [LedgerSpec("TDS Payable - " + section, "Duties & Taxes") for section in _TDS]
    ledgers += [LedgerSpec("Round Off", "Indirect Expenses"), LedgerSpec("Suspense A/c", "Suspense A/c")]
    return ledgers


def plain_explanations() -> dict[str, str]:
    meanings = dict(_EXPENSES)
    meanings.update({
        "Purchases": "Goods or services bought for your business.",
        "Sales": "Money earned by selling your goods or services.",
        "Raw Material Purchases": "Materials bought to make your products.",
        "Freight Inward": "Money spent bringing purchased goods to your business.",
        "Interest Received": "Money earned from savings or lending money.",
        "Discount Received": "Money saved through discounts from suppliers.",
        "Bank Account": "Money held in your business bank account.",
        "Cash": "Physical money held by your business.",
        "Round Off": "Small differences caused by rounding a bill total.",
        "Suspense A/c": "Amounts waiting for someone to confirm what they were for.",
    })
    for tax, head in _DUTIES.items():
        meanings["Input " + tax] = f"{head} GST paid on business purchases, awaiting eligibility review."
        meanings["Output " + tax] = f"{head} GST charged to customers on sales."
    for section in _TDS:
        meanings["TDS Payable - " + section] = f"Tax kept back from payments under {section}, to pay to the government."
    return meanings
