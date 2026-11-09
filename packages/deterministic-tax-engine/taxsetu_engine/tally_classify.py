"""Plain-language entries, always drafts for review."""
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from .money import d, r2
from .tally_models import Line, VoucherDraft

HEADS = (
    (r"bank charges|sms charges|annual fee|gst on charges", "Bank Charges"),
    (r"rent", "Rent Paid"), (r"salary|wages", "Salary and Wages"),
    (r"electricity|bijli|bescom|besl|tata power", "Electricity Charges"),
    (r"internet|phone|airtel|jio|bsnl", "Telephone and Internet"),
    (r"stationery|printing", "Printing and Stationery"),
    (r"repair|maintenance", "Repairs and Maintenance"),
    (r"travel|petrol|diesel", "Travelling Expenses"), (r"insurance", "Insurance"),
    (r"professional|ca fees", "Professional Fees"),
    (r"office", "Office Expenses"), (r"interest|int pd", "Interest Paid"),
)
ALLOWED_HEADS = {head for _, head in HEADS} | {"Interest Received", "Purchases", "Sales"}
SUSPICIOUS = r"\b(?:ignore\s+(?:all\s+)?(?:previous|prior)|post\s+this\s+to|system\s*:|override|disregard|(?:change|set)\s+(?:the\s+)?(?:ledger|amount)\s+to)"
NUMBER = r"\d[\d,]*(?:\.\d+)?\s*(?:lakhs?|lacs?|k\b)?"


def normalise_party(s) -> str:
    s = re.sub(r"\S+@\S+", " ", str(s).lower())
    s = re.sub(r"\bm\s*/\s*s\b|\b(?:mr|mrs|shri)\b", " ", s)
    return " ".join(re.sub(r"[\W\d_]+", " ", s).split())


def learn_alias(ctx, party_text, ledger) -> None:
    if not isinstance(ledger, str) or not ledger.strip() or len(ledger) > 99 or any(ord(c) < 32 or ord(c) == 127 for c in ledger):
        return
    key = normalise_party(party_text)
    if key:
        ctx.aliases[key] = ledger


def _amount(value):
    try:
        s = str(value).lower().replace(",", "").strip()
        multiplier = d(100000) if re.search(r"lakh|lac", s) else d(1000) if s.endswith("k") else d(1)
        amount = d(re.sub(r"\s*(?:lakhs?|lacs?|k)$", "", s)) * multiplier
        return r2(amount) if amount.is_finite() and amount > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value, today):
    s = str(value).strip().lower()
    if s == "today":
        return today
    if s == "yesterday":
        return today - timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d/%m", "%d %B", "%d %b"):
        try:
            # Supply the year first so 29 February works in leap years.
            if fmt in ("%d/%m", "%d %B", "%d %b"):
                return datetime.strptime(f"{s} {today.year}", fmt + " %Y").date()
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def draft_from_text(text, today, ctx, llm=None) -> dict:
    text = str(text or "")
    flags, questions = [], []
    suspicious = re.search(SUSPICIOUS, text, re.I)
    if suspicious:
        flags.append("SUSPICIOUS_TEXT")
    clean = text[:suspicious.start()] if suspicious else text
    lower = clean.lower()
    fields = {}
    date_match = re.search(r"\b(?:yesterday|today|\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}(?:[-/]\d{4})?|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\b", clean, re.I)
    amount_text = clean
    if date_match:
        fields["date"] = _date(date_match.group(), today)
        amount_text = clean[:date_match.start()] + clean[date_match.end():]
    amount_text = re.sub(r"\d+(?:\.\d+)?\s*%", "", amount_text)
    matches = list(re.finditer(NUMBER, amount_text, re.I))
    if len(matches) == 1 and not re.search(r"-\s*" + NUMBER, amount_text, re.I):
        fields["amount"] = _amount(matches[0].group())
    outgoing = bool(re.search(r"\b(paid|gave|bought|spent|purchased)\b", lower))
    incoming = bool(re.search(r"\b(received|got|sold|collected)\b", lower))
    if outgoing != incoming:
        fields["direction"] = "Purchase" if re.search(r"\b(bought|purchased)\b", lower) else "Sales" if re.search(r"\bsold\b", lower) else "Payment" if outgoing else "Receipt"
    if re.search(r"\bcash\b", lower):
        fields["mode"] = "cash"
    elif re.search(r"\b(bank|upi|gpay|phonepe|cheque|check|neft|imps)\b", lower):
        fields["mode"] = "bank"
    for pattern, head in HEADS:
        if re.search(r"\b(?:" + pattern + r")\b", lower):
            fields["head"] = head
            break
    party = re.search(r"\b(?:to|from|by|for)\s+(.+?)(?=\s+\b(?:by|via|using|in|on|today|yesterday|cash|plus|with|to|from)\b|[;,]|$)", clean, re.I)
    if party:
        name = re.sub(r"\b(?:rs\.?|inr|rupees)\b|₹|" + NUMBER, "", party.group(1), flags=re.I).strip(" .-")
        if name and len(name) <= 60 and normalise_party(name) not in {"cash", "cheque", "bank", "upi"}:
            fields["party"] = name
    if llm is not None and not suspicious:
        try:
            extracted = llm.extract_entry(text)
        except Exception:
            extracted = {}
        if isinstance(extracted, dict):
            for key, value in extracted.items():
                if fields.get(key):
                    continue
                if (key == "direction" and outgoing and incoming) or (key == "amount" and matches):
                    continue
                valid = None
                if key == "amount":
                    valid = _amount(value)
                elif key == "date":
                    valid = _date(value, today)
                elif key == "direction" and isinstance(value, str):
                    valid = {"paid": "Payment", "payment": "Payment", "purchase": "Purchase", "receipt": "Receipt", "received": "Receipt", "sale": "Sales", "sales": "Sales"}.get(value.lower())
                elif key == "head" and isinstance(value, str) and value in ALLOWED_HEADS:
                    valid = value
                elif key == "mode" and isinstance(value, str) and value.lower() in {"cash", "bank", "upi", "cheque", "gpay", "phonepe"}:
                    valid = "cash" if value.lower() == "cash" else "bank"
                elif key == "party" and isinstance(value, str) and 0 < len(value.strip()) <= 60 and not re.search(SUSPICIOUS, value, re.I) and not any(ord(c) < 32 for c in value):
                    valid = value.strip()
                if valid is not None:
                    fields[key] = valid
    amount, direction = fields.get("amount"), fields.get("direction")
    if not amount:
        questions.append("What is the amount of this entry?")
    if not direction:
        questions.append("Did you pay or receive this money?")
    if date_match and not fields.get("date"):
        questions.append("What is the correct date?")
    if direction in {"Sales", "Purchase"} and not fields.get("party"):
        questions.append("Who did you buy from or sell to?")
    if not fields.get("party") and not fields.get("head") and direction in {"Payment", "Receipt"}:
        questions.append("Who was this payment to or receipt from?")
    if questions:
        return {"draft": None, "questions": questions, "flags": flags, "interpretation": "More details are needed to draft this entry."}
    party_name = fields.get("party", "")
    alias = ctx.aliases.get(normalise_party(party_name))
    ledger = alias or fields.get("head") or party_name
    if direction == "Receipt" and ledger == "Interest Paid":
        ledger = "Interest Received"
    if direction in {"Sales", "Purchase"}:
        ledger = alias or party_name
    if ledger == party_name and party_name and not alias and ledger not in ctx.known_ledgers:
        flags.append("NEW_LEDGER:" + ledger)
    side = "Dr" if direction in {"Payment", "Purchase"} else "Cr"
    opposite = "Cr" if side == "Dr" else "Dr"
    if direction in {"Sales", "Purchase"}:
        lines = [Line("Purchases" if direction == "Purchase" else "Sales", amount, side)]
        if re.search(r"\bgst\b", lower):
            rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*gst", lower)
            rate = _amount(rate_match.group(1)) if rate_match else _amount(ctx.default_gst_rate)
            if rate is None or rate > 100:
                return {"draft": None, "questions": ["What GST rate should apply?"], "flags": flags, "interpretation": "GST rate needs confirmation."}
            tax = r2(amount * rate / 100)
            half = r2(tax / 2)
            prefix = "Input" if direction == "Purchase" else "Output"
            lines.extend(Line(prefix + " " + name, value, side) for name, value in (("CGST", half), ("SGST", tax - half)) if value > 0)
            amount += tax
            flags.append("GST_ASSUMED_INTRASTATE")
        lines.append(Line(ledger, amount, opposite))
    else:
        account = ctx.cash_ledger if fields.get("mode") == "cash" else ctx.bank_ledger
        lines = [Line(ledger, amount, side), Line(account, amount, opposite)]
    draft = VoucherDraft(direction, fields.get("date") or today, tuple(lines), party=ledger, narration=clean.strip(), place_of_supply=ctx.state_code,
                         confidence=Decimal("0.95") if alias else Decimal("0.75"), source="text", flags=tuple(flags))
    return {"draft": draft, "questions": [], "flags": flags, "interpretation": f"Draft {direction}: {amount:.2f} for {ledger}."}
