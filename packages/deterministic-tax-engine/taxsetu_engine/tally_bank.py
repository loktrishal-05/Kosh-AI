"""Bank CSV import and draft categorisation. No posting."""
import csv
import hashlib
import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .money import d, r2
from .tally_classify import HEADS, normalise_party
from .tally_models import BankTxn, Line, VoucherDraft


def _date(value):
    for fmt in ("%d/%m/%Y", "%d-%m-%y", "%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _money(value):
    value = value.strip().replace(",", "")
    if not value or value == "-":
        return Decimal(0)
    value = re.sub(r"\s*(?:dr|cr)$", "", value, flags=re.I).strip()
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("() ")
    amount = d(value)
    if not amount.is_finite():
        raise ValueError("non-finite amount")
    amount = r2(amount)
    return -abs(amount) if negative else amount


def parse_statement_csv(text) -> dict:
    txns, errors, skipped = [], [], 0
    columns = None
    try:
        rows = csv.reader(io.StringIO(str(text or "").lstrip("\ufeff")), strict=True)
        for row_number, row in enumerate(rows, 1):
            if not any(cell.strip() for cell in row):
                skipped += 1
                continue
            if columns is None:
                found = {}
                for i, cell in enumerate(row):
                    label = re.sub(r"[^a-z]+", " ", cell.lower()).strip()
                    if "date" in label and "value" not in label:
                        found.setdefault("date", i)
                    elif re.search(r"narration|description|particulars", label):
                        found["narration"] = i
                    elif re.search(r"dr\s*cr|debit\s*credit|transaction type", label):
                        found["side"] = i
                    elif re.search(r"debit|withdrawal", label):
                        found["debit"] = i
                    elif re.search(r"credit|deposit", label):
                        found["credit"] = i
                    elif "balance" in label:
                        found["balance"] = i
                    elif "amount" in label:
                        found["amount"] = i
                    elif re.search(r"chq|cheque|ref|utr", label):
                        found["ref"] = i
                if {"date", "narration"} <= found.keys() and ("amount" in found or {"debit", "credit"} <= found.keys()):
                    columns = found
                else:
                    skipped += 1
                continue
            def cell(name):
                index = columns.get(name)
                return row[index].strip() if index is not None and index < len(row) else ""
            when = _date(cell("date"))
            if when is None:
                if any(cell(name) for name in ("debit", "credit", "amount")) and not re.search(r"total|closing|opening|balance|end of|generated", " ".join(row), re.I):
                    errors.append(f"Row {row_number}: invalid date.")
                else:
                    skipped += 1
                continue
            try:
                if "amount" in columns:
                    raw = cell("amount")
                    amount = _money(raw)
                    marker = cell("side").lower() or (re.search(r"(dr|cr)\s*$", raw, re.I).group(1).lower() if re.search(r"(dr|cr)\s*$", raw, re.I) else "")
                    if "side" in columns and marker not in {"dr", "cr", "debit", "credit"}:
                        raise ValueError("missing Dr/Cr")
                    out = marker in {"dr", "debit"} or (not marker and amount < 0)
                    debit, credit = (abs(amount), Decimal(0)) if out else (Decimal(0), abs(amount))
                else:
                    debit, credit = _money(cell("debit")), _money(cell("credit"))
                if debit < 0 or credit < 0 or bool(debit) == bool(credit):
                    raise ValueError("expected exactly one positive debit or credit")
                balance = _money(cell("balance")) if cell("balance") else None
                narration = " ".join(cell("narration").split())
                ref = cell("ref") or _reference(narration)
                payload = [when.isoformat(), narration, format(debit, ".2f"), format(credit, ".2f"), ref]
                key = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
                txns.append(BankTxn(when, narration, debit, credit, balance, ref, key))
            except (InvalidOperation, ValueError):
                errors.append(f"Row {row_number}: invalid amounts.")
    except csv.Error:
        errors.append("Malformed CSV data.")
    if columns is None:
        errors.append("Could not find a bank statement header.")
    return {"txns": txns, "errors": errors, "skipped": skipped}


def dedupe(txns, seen_keys) -> list:
    seen, result = set(seen_keys), []
    for txn in txns:
        if txn.key not in seen:
            result.append(txn)
            seen.add(txn.key)
    return result


def _reference(narration):
    match = re.search(r"\b(?:UTR|CHQ|CHEQUE|REF)\s*[:/#-]?\s*([A-Z0-9]{3,})\b|\b(?:UPI|NEFT|IMPS|RTGS)[/ -]+([A-Z0-9]*\d[A-Z0-9]*)", narration, re.I)
    return next((v for v in match.groups() if v), "") if match else ""


def _party(narration):
    value = re.sub(r"\bPAYMENT\s+(?:FROM|TO)\s+", "", narration, flags=re.I)
    parts = re.split(r"[/|]", value)
    if len(parts) == 1:
        parts = re.split(r"\s*-\s*", value)
    for part in parts[1:]:
        part = re.sub(r"^(?:TO|FROM)\s+", "", part.strip(), flags=re.I)
        if re.search(r"[a-z]", part, re.I) and not re.fullmatch(r"[A-Z]*\d+[A-Z0-9]*|ok\w+|\S+@\S+|UPI|NEFT|IMPS|RTGS|CHQ|POS|ACH|ECS", part, re.I):
            return part
    return value.strip() if len(parts) == 1 else ""


def to_drafts(txns, ctx) -> list:
    drafts = []
    for txn in txns:
        text = " ".join(txn.narration.split())
        lower = text.lower()
        outgoing = txn.debit > 0
        amount = txn.debit if outgoing else txn.credit
        ledger, confidence, flags = "Suspense A/c", Decimal("0.4"), []
        party = _party(text)
        alias = ctx.aliases.get(normalise_party(party)) or ctx.aliases.get(normalise_party(text))
        contra = bool(re.search(r"\batm\b|cash\s*(?:wdl|withdrawal|deposit)|deposit\s+cash", lower))
        if alias:
            ledger, confidence = alias, Decimal("0.95")
            contra = False
        elif contra:
            ledger, confidence = ctx.cash_ledger, Decimal("0.9")
        elif re.search(r"\b(?:emi|loan)\b", lower):
            ledger, confidence = "Interest Paid", Decimal("0.7")
            flags.append("NEEDS_REVIEW")
        elif re.search(r"\bint pd\b|interest credit|interest", lower):
            ledger, confidence = ("Interest Paid" if outgoing else "Interest Received"), Decimal("0.85")
        else:
            for pattern, head in HEADS:
                if re.search(r"\b(?:" + pattern + r")\b", lower):
                    ledger, confidence = head, Decimal("0.85")
                    if not outgoing and head not in ("Bank Charges", "Interest Paid"):
                        confidence = Decimal("0.5")      # money IN under an expense keyword (rent received? refund?): a person must decide
                        flags.append("NEEDS_REVIEW")
                    break
        if ledger == "Suspense A/c":
            flags.append("NEEDS_REVIEW")
        side = "Dr" if outgoing else "Cr"
        lines = (Line(ledger, amount, side), Line(ctx.bank_ledger, amount, "Cr" if outgoing else "Dr"))
        drafts.append(VoucherDraft("Contra" if contra else "Payment" if outgoing else "Receipt", txn.date, lines,
                                   party=ledger, narration=text, reference=txn.ref or _reference(text), confidence=confidence,
                                   source="bank_csv", flags=tuple(flags)))
    return drafts


def summary(drafts) -> dict:
    drafts = list(drafts)
    ready = sum(v.confidence >= Decimal("0.8") and "NEEDS_REVIEW" not in v.flags for v in drafts)
    # Bank drafts put the bank entry second, including both Contra directions.
    return {"count": len(drafts), "auto_ready": ready, "needs_review": len(drafts) - ready,
            "total_in": sum((v.lines[1].amount for v in drafts if v.lines[1].side == "Dr"), Decimal(0)),
            "total_out": sum((v.lines[1].amount for v in drafts if v.lines[1].side == "Cr"), Decimal(0))}
