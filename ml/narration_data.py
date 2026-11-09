"""Synthetic training data for the bank-narration classifier (no real customer data is used or stored).

A bank-statement row such as "UPI/DR/412345678901/BESCOM/okhdfcbank/Bill Pay" is labelled with the ledger head a shop owner would file it under.
Every label has a pool of phrases and merchants. The LAST fifth of each pool is held back for the test set only, so the test measures
whether the model handles phrases it never saw in training (typos, case, bank formats and reference numbers are randomised for both).
Pure standard library so the same file runs inside the Colab notebook.
"""
import random

LABELS = ["Bank Charges", "Electricity Charges", "Insurance", "Interest Paid", "Interest Received", "Office Expenses", "Other", "Printing and Stationery",
          "Professional Fees", "Purchases", "Rent Paid", "Repairs and Maintenance", "Salary and Wages", "Sales", "Telephone and Internet", "Travelling Expenses"]
INCOMING = {"Sales", "Interest Received"}          # the other labels are normally money going out; "Other" occurs in both directions

POOL = {
    "Bank Charges": ["SMS CHARGES", "SMS ALERT CHGS", "ANNUAL FEE", "CHQ BOOK ISSUE CHGS", "MIN BAL PENALTY", "GST ON CHARGES", "DEBIT CARD AMC", "BANK CHARGES",
                     "NEFT CHARGES", "IMPS CHG", "ATM ANNUAL FEE", "ACCOUNT MAINTENANCE CHG", "CASH HANDLING CHARGES", "RTGS CHARGES"],
    "Electricity Charges": ["BESCOM", "MSEDCL", "TATA POWER", "BSES RAJDHANI", "TNEB", "KSEB", "TORRENT POWER", "ELECTRICITY BILL", "BIJLI BILL", "POWER BILL",
                            "CESC", "ADANI ELECTRICITY", "UPPCL", "JBVNL", "BESL", "HESCOM", "DHBVN", "NPCL"],
    "Insurance": ["LIC PREMIUM", "INSURANCE PREMIUM", "HDFC LIFE", "ICICI LOMBARD", "STAR HEALTH", "NEW INDIA ASSURANCE", "VEHICLE INSURANCE", "FIRE POLICY",
                  "BAJAJ ALLIANZ", "POLICY RENEWAL", "MAX LIFE", "ORIENTAL INSURANCE", "SHOP INSURANCE", "SBI GENERAL"],
    "Interest Paid": ["INT PD", "LOAN INTEREST", "INTEREST DEBITED", "OD INTEREST", "CC INTEREST", "EMI INTEREST PART", "INTEREST ON LOAN", "INT.PD",
                      "INTEREST CHARGED", "TERM LOAN INTEREST", "INT ON CASH CREDIT", "INTEREST DEBIT"],
    "Interest Received": ["INT CR", "INTEREST CREDITED", "SAVINGS INTEREST", "FD INTEREST", "INT.PAID TILL", "INTEREST RECEIVED", "SB INT", "QUARTERLY INTEREST CREDIT",
                          "INT ON FD", "INTEREST PAYOUT", "RD INTEREST", "CREDIT INTEREST"],
    "Office Expenses": ["OFFICE TEA", "PANTRY ITEMS", "OFFICE CLEANING", "HOUSEKEEPING", "OFFICE SUPPLIES", "WATER CAN", "OFFICE EXPENSES", "CHAI AND SNACKS",
                        "OFFICE MISC", "DRINKING WATER", "OFFICE REFRESHMENTS", "SWEEPER CHARGES"],
    "Printing and Stationery": ["STATIONERY", "XEROX", "PHOTOCOPY", "PRINTING CHARGES", "PAPER REAMS", "PEN AND FILES", "OFFICE STATIONERY", "VISITING CARDS PRINT",
                                "FLEX PRINTING", "KOKUYO", "CAMLIN", "BILL BOOK PRINTING", "LETTERHEAD PRINTING", "CLASSMATE NOTEBOOKS"],
    "Professional Fees": ["CA FEES", "AUDIT FEES", "LEGAL FEES", "ADVOCATE FEES", "CONSULTANT FEES", "PROFESSIONAL CHARGES", "GST RETURN FILING FEES", "TAX CONSULTANT",
                          "COMPANY SECRETARY FEES", "ROC FILING CHARGES", "ACCOUNTANT FEES", "BOOK KEEPING CHARGES", "TDS RETURN FEES", "ITR FILING FEES"],
    "Purchases": ["PURCHASE OF GOODS", "STOCK PURCHASE", "RAW MATERIAL", "SUPPLIER INVOICE", "WHOLESALE PURCHASE", "MATERIAL PURCHASE", "GOODS PAYMENT", "MERCHANDISE",
                  "SHREE TRADERS", "GUPTA AGENCIES", "BALAJI DISTRIBUTORS", "SAI ENTERPRISES", "MAHALAXMI WHOLESALE", "KRISHNA SUPPLIERS", "METRO CASH AND CARRY",
                  "UDAAN", "JUMBOTAIL", "OM TRADING CO", "SURESH WHOLESALERS", "STOCK PAYMENT"],
    "Rent Paid": ["SHOP RENT", "OFFICE RENT", "HOUSE RENT", "RENT FOR APRIL", "GODOWN RENT", "KIRAYA", "MONTHLY RENT", "RENT PAYMENT", "LEASE RENT", "WAREHOUSE RENT",
                  "RENT TO LANDLORD", "PREMISES RENT", "RENT FOR SHOP", "RENT MAY"],
    "Repairs and Maintenance": ["REPAIR", "AC REPAIR", "PLUMBER", "ELECTRICIAN", "MAINTENANCE CHARGES", "AMC SERVICE", "COMPUTER REPAIR", "MISTRI", "PAINTING WORK",
                                "LIFT MAINTENANCE", "SERVICING", "SHUTTER REPAIR", "REPAIRS AND MAINTENANCE", "CARPENTER CHARGES"],
    "Salary and Wages": ["SALARY", "WAGES", "SALARY FOR MARCH", "STAFF SALARY", "PAYROLL", "LABOUR WAGES", "MAZDOORI", "DAILY WAGES", "SALARY ADVANCE", "SALARIES",
                         "STAFF PAYMENT", "WORKER WAGES", "MONTHLY SALARY", "LOADING UNLOADING LABOUR"],
    "Sales": ["SALES", "CUSTOMER PAYMENT", "POS SETTLEMENT", "RAZORPAY SETTLEMENT", "PAYTM SETTLEMENT", "PHONEPE SETTLEMENT", "INVOICE RECEIPT", "BILL PAYMENT RECEIVED",
              "SALES COLLECTION", "UPI COLLECTION", "CARD SETTLEMENT", "CASHFREE SETTLEMENT", "BHARATPE SETTLEMENT", "SALE PROCEEDS", "PAYMENT AGAINST INVOICE", "QR COLLECTION"],
    "Telephone and Internet": ["AIRTEL", "JIO", "BSNL", "VODAFONE IDEA", "VI POSTPAID", "ACT FIBERNET", "HATHWAY BROADBAND", "MOBILE RECHARGE", "BROADBAND BILL",
                               "TELEPHONE BILL", "INTERNET CHARGES", "TATA PLAY FIBER", "JIOFIBER", "LANDLINE BILL", "WIFI BILL", "DATA RECHARGE"],
    "Travelling Expenses": ["PETROL", "DIESEL", "HPCL", "IOCL", "BPCL", "SHELL FUEL", "OLA CABS", "UBER", "IRCTC", "REDBUS", "FASTAG RECHARGE", "TOLL", "TRAVEL",
                            "AUTO FARE", "FLIGHT TICKET", "INDIGO", "TRAIN TICKET", "FUEL PUMP", "TAXI FARE", "BUS TICKET"],
    "Other": ["TRANSFER TO SELF", "ATM WDL", "CASH WITHDRAWAL", "FD BOOKING", "MF SIP", "FAMILY TRANSFER", "ZOMATO", "SWIGGY", "AMAZON PAY", "PERSONAL", "GIFT",
              "LOAN FROM FRIEND", "CHEQUE DEPOSIT", "UNKNOWN", "SELF", "MYNTRA", "BOOKMYSHOW", "SCHOOL FEES", "GROCERIES HOME", "DONATION TEMPLE", "MEDICAL STORE"],
}
PEOPLE = ["RAMESH KUMAR", "S REDDY", "MRS IYER", "P SHARMA", "M/S GUPTA PROPERTIES", "R PATEL", "ANITA SINGH", "MOHAN LAL", "K VENKATESH", "SUNITA DEVI",
          "ABDUL RAHIM", "J D'SOUZA", "VIKRAM JOSHI", "LAKSHMI NAIR", "BHARAT TRADERS", "NEHA VERMA", "GURPREET SINGH", "T MURUGAN"]
PERSON_LABELS = {"Rent Paid", "Salary and Wages", "Repairs and Maintenance", "Professional Fees", "Purchases", "Sales", "Other"}
NOTES = ["", "", "", "BILL", "PAYMENT", "MAR 2026", "APR 26", "INV 4821", "REF", "ONLINE", "THANKS", "FEB", "Q3", "NO 12", "PAID", "HELP"]
BANKS = ["okhdfcbank", "oksbi", "okicici", "ybl", "paytm", "axl", "ibl", "upi", "apl"]
IFSC = ["HDFC0001234", "SBIN0004567", "ICIC0002345", "CNRB0001122", "UTIB0000987", "PUNB0123400", "KKBK0000571", "BARB0KORAMA"]
OUT_FORMATS = ["UPI/DR/{ref}/{m}/{vpa}/{note}", "NEFT-{ifsc}-{m}-{note}", "IMPS/P2A/{ref}/{m}", "POS {card} {m}", "ACH D- {m}-{ref}", "{m}", "{note} {m}", "BILLPAY {m} {ref}",
               "CHQ PAID {ref} {m}", "{m} {note}", "PAID TO {m} FOR {note}", "{note} - {m}", "ONLINE PMT {m}", "UPI-{m}-{vpa}-{ref}-{note}", "DEBIT {m} {ref}", "BY CASH {m}"]
IN_FORMATS = ["UPI/CR/{ref}/{m}/{vpa}", "NEFT CR-{ifsc}-{m}-{note}", "IMPS/{ref}/{m}", "BY TRANSFER-{m}", "CREDIT {m} {ref}", "{m}", "{note} {m}", "{m} {note}",
              "UPI-{m}-{vpa}-{ref}", "RTGS CR {ifsc} {m}", "INW {m} {ref}"]


def split_pool(label):
    pool = POOL[label]
    cut = len(pool) - max(2, len(pool) // 5)
    return pool[:cut], pool[cut:]


def _noise(rng, s):
    s = rng.choice((s, s, s.lower(), s.title()))
    if len(s) > 4 and rng.random() < 0.12:               # a typo: drop or swap a letter
        i = rng.randrange(1, len(s) - 1)
        s = s[:i] + s[i + 1:] if rng.random() < 0.5 else s[:i] + s[i + 1] + s[i] + s[i + 2:]
    return s


def _one(rng, label, part):
    train, held = split_pool(label)
    phrase = rng.choice(train if part == "train" else held)
    if label in PERSON_LABELS and rng.random() < 0.35:
        who = rng.choice(PEOPLE)
        phrase = f"{who} {phrase}" if rng.random() < 0.5 else f"{phrase} {who}"
    incoming = label in INCOMING or (label == "Other" and rng.random() < 0.4)
    ref = str(rng.randrange(10 ** 8, 10 ** 12))
    text = rng.choice(IN_FORMATS if incoming else OUT_FORMATS).format(
        m=phrase, ref=ref, vpa=f"{rng.choice(PEOPLE).split()[0].lower()}@{rng.choice(BANKS)}", note=rng.choice(NOTES), ifsc=rng.choice(IFSC),
        card=f"{rng.randrange(4000, 6000)}XXXXXXXX{rng.randrange(1000, 9999)}")
    text = " ".join(_noise(rng, text).split())
    return {"text": ("in | " if incoming else "out | ") + text, "label": label}


def make(seed=7, n_train=40000, n_test=4000):
    """(train, test): lists of {"text", "label"}. Test rows use only the held-back phrases of each label."""
    rng = random.Random(seed)
    train = [_one(rng, LABELS[i % len(LABELS)], "train") for i in range(n_train)]
    test = [_one(rng, LABELS[i % len(LABELS)], "test") for i in range(n_test)]
    rng.shuffle(train)
    return train, test


if __name__ == "__main__":
    a, b = make(1, 6, 3)
    for r in a + b:
        print(r["label"].ljust(26), r["text"])
