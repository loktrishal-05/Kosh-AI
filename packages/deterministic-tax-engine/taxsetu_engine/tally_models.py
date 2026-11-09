"""Shared contract for the Tally autopilot (engine, API, bridge). Pure data: no I/O, no Tally sign rules (those live in tallybooks).
All money is Decimal and always positive; direction is carried by `side`."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

VOUCHER_TYPES = ("Sales", "Purchase", "Payment", "Receipt", "Journal", "Contra")
SIDES = ("Dr", "Cr")
SOURCES = ("manual", "text", "bank_csv", "invoice", "voice")


@dataclass(frozen=True)
class Line:
    ledger: str
    amount: Decimal
    side: str                      # "Dr" | "Cr"


@dataclass(frozen=True)
class VoucherDraft:
    vtype: str                     # one of VOUCHER_TYPES
    date: date
    lines: tuple = ()              # tuple[Line, ...]
    number: str = ""
    party: str = ""                # party ledger name (Sales / Purchase / Receipt / Payment)
    narration: str = ""
    reference: str = ""            # supplier invoice number for Purchase
    reference_date: date | None = None
    party_gstin: str = ""
    place_of_supply: str = ""      # 2-digit GST state code
    confidence: Decimal = Decimal("1")      # 0..1, how sure the classifier is
    source: str = "manual"
    flags: tuple = ()              # e.g. ("NEW_LEDGER:Sharma Traders", "GSTIN_MISSING", "NEEDS_REVIEW")

    def total_dr(self) -> Decimal:
        return sum((l.amount for l in self.lines if l.side == "Dr"), Decimal(0))

    def total_cr(self) -> Decimal:
        return sum((l.amount for l in self.lines if l.side == "Cr"), Decimal(0))

    def balanced(self) -> bool:
        return bool(self.lines) and self.total_dr() == self.total_cr()


@dataclass(frozen=True)
class LedgerSpec:
    name: str
    parent: str                    # Tally group, e.g. "Sundry Creditors", "Duties & Taxes", "Bank Accounts"
    gstin: str = ""
    state: str = ""
    gst_duty_head: str = ""        # "Central Tax" | "State Tax" | "Integrated Tax" for GST duty ledgers
    gst_registration_type: str = ""  # "Regular" | "Unregistered/Consumer" | "Composition" ...


@dataclass(frozen=True)
class BankTxn:
    date: date
    narration: str
    debit: Decimal = Decimal(0)    # money out of the account
    credit: Decimal = Decimal(0)   # money into the account
    balance: Decimal | None = None
    ref: str = ""                  # cheque / UTR / reference number if present
    key: str = ""                  # stable dedup hash, set by the parser


@dataclass
class BookContext:
    """What the classifier knows about this business. `aliases` maps a normalised counterparty phrase to a ledger name."""
    company: str = ""
    state_code: str = ""           # business GST state code, e.g. "29"
    bank_ledger: str = "Bank Account"
    cash_ledger: str = "Cash"
    aliases: dict = field(default_factory=dict)
    known_ledgers: set = field(default_factory=set)
    default_gst_rate: Decimal = Decimal("18")


def draft_to_dict(v: VoucherDraft) -> dict:
    return {"vtype": v.vtype, "date": v.date.isoformat(), "number": v.number, "party": v.party, "narration": v.narration,
            "reference": v.reference, "reference_date": v.reference_date.isoformat() if v.reference_date else None,
            "party_gstin": v.party_gstin, "place_of_supply": v.place_of_supply, "confidence": str(v.confidence),
            "source": v.source, "flags": list(v.flags),
            "lines": [{"ledger": l.ledger, "amount": str(l.amount), "side": l.side} for l in v.lines]}


def draft_from_dict(d: dict) -> VoucherDraft:
    """Strict: raises ValueError/KeyError on anything malformed (callers turn that into a 422)."""
    if d["vtype"] not in VOUCHER_TYPES:
        raise ValueError(f"unknown voucher type {d['vtype']!r}")
    lines = []
    for l in d.get("lines", []):
        if l["side"] not in SIDES:
            raise ValueError("side must be Dr or Cr")
        amt = Decimal(str(l["amount"]))
        if not amt.is_finite() or amt <= 0:
            raise ValueError("line amount must be a positive number")
        lines.append(Line(str(l["ledger"]), amt, l["side"]))
    ref_date = d.get("reference_date")
    return VoucherDraft(
        vtype=d["vtype"], date=date.fromisoformat(d["date"]), lines=tuple(lines), number=str(d.get("number", "")),
        party=str(d.get("party", "")), narration=str(d.get("narration", "")), reference=str(d.get("reference", "")),
        reference_date=date.fromisoformat(ref_date) if ref_date else None, party_gstin=str(d.get("party_gstin", "")),
        place_of_supply=str(d.get("place_of_supply", "")), confidence=Decimal(str(d.get("confidence", "1"))),
        source=d.get("source", "manual") if d.get("source", "manual") in SOURCES else "manual", flags=tuple(d.get("flags", ())))
