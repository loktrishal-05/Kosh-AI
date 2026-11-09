"""Single-entry books: turn a cash book into proper double-entry accounts and keep them over time.
  /books/sandbox/*  anonymous and stateless: try the conversion with your own figures or a bundled real-time example
  /books/*          signed-in: create a book, add entries (type or CSV), correct by voiding, see the reports, close the period,
                    roll the balances into the next period, and send the result to Tally through the existing approval queue.
Nothing is ever deleted: a wrong line is voided with a reason and the audit chain records who did what."""
import hashlib
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from taxsetu_engine import single_entry as se
from taxsetu_engine import tallybooks

EXAMPLES = Path(__file__).parent / "examples"
EXAMPLE_TITLES = {
    "business_textbook": ("A shop's year, textbook style", "Ravi General Stores: credit sales and purchases are not in the cash book; the conversion finds them."),
    "kirana_full_year": ("A busy kirana store, 12 months", "About 180 cash-book lines with credit customers, suppliers, a loan, a new asset and a bad debt."),
    "nonprofit_club": ("A youth club (receipts and payments)", "Sunrise Youth Club: subscriptions in arrears and in advance, a corpus donation, depreciation."),
    "individual_freelancer": ("A freelancer's household", "Income, spending, investments and a home loan; shows savings and net worth."),
}
SANDBOX_ENTRIES, BOOK_ENTRIES, TALLY_CHUNK = 1000, 2000, 400
WRITERS, DECIDERS = ("OWNER", "CA", "CLERK", "EMPLOYEE"), ("OWNER", "CA")
SIMPLE = ("cash", "bank", "debtors", "creditors", "stock", "fixed_assets", "investments", "loans", "capital")
HEADS = ("outstanding_expenses", "prepaid_expenses", "accrued_income", "advance_income")
CLOSING_SIMPLE = ("debtors", "creditors", "stock", "discount_allowed", "discount_received", "bad_debts", "sales_returns", "purchase_returns",
                  "depreciation", "depreciation_rate", "investments_market_value")


def _num(v, field, allow_negative=False) -> str:
    try:
        x = Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(422, f"{field}: '{v}' is not a number")
    if not x.is_finite() or abs(x) >= Decimal("1e13") or (x < 0 and not allow_negative):
        raise HTTPException(422, f"{field}: amount is out of range")
    return format(x.quantize(Decimal("0.01")), "f")


def clean_figures(raw: dict | None, simple: tuple, label: str) -> dict:
    """Only known keys, numeric values, per-head dicts of numbers: nothing else reaches the converter or the database."""
    out = {}
    for k, v in (raw or {}).items():
        if k in simple:
            if v not in (None, ""):
                out[k] = _num(v, f"{label}.{k}", allow_negative=(k == "capital"))
        elif k in HEADS:
            if not isinstance(v, dict) or len(v) > 50:
                raise HTTPException(422, f"{label}.{k} must be a list of head: amount")
            out[k] = {str(h)[:60]: _num(a, f"{label}.{k}.{h}") for h, a in v.items()}
        else:
            raise HTTPException(422, f"{label}: unknown field '{k}'")
    return out


class EntryIn(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=200)
    receipt: Decimal = Field(default=Decimal(0), ge=0, lt=Decimal("1e13"))
    payment: Decimal = Field(default=Decimal(0), ge=0, lt=Decimal("1e13"))
    mode: str = Field(default="cash", pattern="^(cash|bank)$")
    party: str = Field(default="", max_length=80)
    hint: str = Field(default="", max_length=60)


def entry_record(e: EntryIn, i: int) -> dict:
    if (e.receipt > 0) == (e.payment > 0):
        raise HTTPException(422, f"line {i}: enter either money in or money out, not both and not neither")
    q = lambda x: format(x.quantize(Decimal("0.01")), "f")
    return {"date": e.date.isoformat(), "description": e.description.strip(), "receipt": q(e.receipt), "payment": q(e.payment),
            "mode": e.mode, "party": e.party.strip(), "hint": e.hint.strip()}


class BookIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    entity_type: str = Field(pattern="^(business|individual|nonprofit)$")
    period_start: date
    period_end: date
    opening: dict = Field(default_factory=dict)
    closing: dict = Field(default_factory=dict)


class SetupIn(BaseModel):
    opening: dict | None = None
    closing: dict | None = None


class AddIn(BaseModel):
    entries: list[EntryIn] = Field(default_factory=list, max_length=BOOK_ENTRIES)
    csv: str = Field(default="", max_length=600_000)


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


class CloseIn(BaseModel):
    accept_review: bool = False


class RolloverIn(BaseModel):
    period_end: date | None = None


class TallyIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    accept_review: bool = False


class SandboxBook(BaseModel):
    book: dict


class CsvIn(BaseModel):
    csv: str = Field(min_length=1, max_length=600_000)


def book_for_convert(book: dict, entries: list) -> dict:
    return {"entity_type": book["entity_type"], "name": book["name"], "period_start": book["period_start"], "period_end": book["period_end"],
            "opening": book.get("opening") or {}, "closing": book.get("closing") or {},
            "entries": [{k: e.get(k, "") for k in ("date", "description", "receipt", "payment", "mode", "party", "hint")} for e in entries]}


def carry_forward(book: dict, result: dict) -> dict:
    """Opening balances for the next period, read from the closed books (post-closing ledgers) plus the per-head year-end figures."""
    def bal(name):
        row = result["ledgers"].get(name)
        return Decimal(0) if not row else (Decimal(row["balance"]) if row["side"] == "Dr" else -Decimal(row["balance"]))
    fmt = lambda x: format(x.quantize(Decimal("0.01")), "f")
    op = {"cash": bal("Cash"), "bank": bal("Bank"), "debtors": bal("Debtors"), "creditors": -bal("Creditors"), "stock": bal("Stock-in-Trade"),
          "fixed_assets": bal("Fixed Assets"), "investments": bal("Investments"), "loans": -bal("Loans")}
    out = {k: fmt(v) for k, v in op.items() if v != 0}
    for k in HEADS:
        if (book.get("closing") or {}).get(k):
            out[k] = dict(book["closing"][k])
    return out


def mount(app, *, gate, books, need) -> None:
    audit = gate.audit

    def example(name: str) -> dict:
        return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))

    # ---- sandbox: anonymous, stateless --------------------------------------------------------------------------------
    @app.get("/api/v1/books/sandbox/examples", tags=["books-sandbox"])
    def examples():
        return {"examples": [{"id": k, "title": t, "description": d, "entity_type": example(k)["entity_type"], "entries": len(example(k)["entries"])}
                             for k, (t, d) in EXAMPLE_TITLES.items() if (EXAMPLES / f"{k}.json").exists()]}

    @app.get("/api/v1/books/sandbox/examples/{name}", tags=["books-sandbox"])
    def one_example(name: str):
        if name not in EXAMPLE_TITLES or not (EXAMPLES / f"{name}.json").exists():
            raise HTTPException(404, "no such example")
        return {"id": name, "title": EXAMPLE_TITLES[name][0], "book": example(name)}

    def checked_book(raw: dict, limit: int) -> dict:
        if not isinstance(raw, dict) or raw.get("entity_type") not in ("business", "individual", "nonprofit"):
            raise HTTPException(422, "entity_type must be business, individual or nonprofit")
        entries = raw.get("entries", [])
        if not isinstance(entries, list) or len(entries) > limit:
            raise HTTPException(422, f"at most {limit} lines")
        try:
            start, end = date.fromisoformat(str(raw.get("period_start"))), date.fromisoformat(str(raw.get("period_end")))
        except ValueError:
            raise HTTPException(422, "period_start and period_end must be dates (YYYY-MM-DD)")
        if end < start or (end - start).days > 400:
            raise HTTPException(422, "the period must be between 1 and 400 days")
        clean = []
        for i, e in enumerate(entries, 1):
            try:
                clean.append(entry_record(EntryIn(date=e.get("date"), description=str(e.get("description", "")), receipt=e.get("receipt") or 0,
                                                  payment=e.get("payment") or 0, mode=e.get("mode") or "cash", party=str(e.get("party", "")),
                                                  hint=str(e.get("hint", ""))), i))
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(422, f"line {i}: could not read this line (date, description and one amount are needed)")
        return {"entity_type": raw["entity_type"], "name": str(raw.get("name", ""))[:120] or "My books", "period_start": start.isoformat(), "period_end": end.isoformat(),
                "opening": clean_figures(raw.get("opening"), SIMPLE, "opening"), "closing": clean_figures(raw.get("closing"), CLOSING_SIMPLE, "closing"), "entries": clean}

    @app.post("/api/v1/books/sandbox/convert", tags=["books-sandbox"])
    def sandbox_convert(b: SandboxBook):
        return se.convert(checked_book(b.book, SANDBOX_ENTRIES))

    @app.post("/api/v1/books/sandbox/parse-csv", tags=["books-sandbox"])
    def sandbox_csv(b: CsvIn):
        return se.parse_cash_book_csv(b.csv)

    # ---- signed in: keep books over time ----------------------------------------------------------------------------
    def get_book(c: dict, book_id: str) -> dict:
        b = books.book_get(c["tenant_id"], book_id)
        if not b:
            raise HTTPException(404, "book not found")
        return b

    def report_for(c: dict, b: dict) -> dict:
        if b["status"] == "CLOSED" and b.get("closed_report"):
            return b["closed_report"]
        return se.convert(book_for_convert(b, books.entry_list(c["tenant_id"], b["book_id"])))

    @app.post("/api/v1/books", tags=["books"])
    def create(b: BookIn, c: dict = Depends(need(*WRITERS))):
        if b.period_end < b.period_start or (b.period_end - b.period_start).days > 400:
            raise HTTPException(422, "the period must be between 1 and 400 days")
        rec = books.book_add(c["tenant_id"], {"name": b.name.strip(), "entity_type": b.entity_type, "period_start": b.period_start.isoformat(),
                                              "period_end": b.period_end.isoformat(), "opening": clean_figures(b.opening, SIMPLE, "opening"),
                                              "closing": clean_figures(b.closing, CLOSING_SIMPLE, "closing")})
        audit.append(c["tenant_id"], c["role"], "BOOK_CREATED", book_id=rec["book_id"], entity_type=b.entity_type)
        return rec

    @app.get("/api/v1/books", tags=["books"])
    def listing(c: dict = Depends(need(*WRITERS))):
        return {"books": [{k: v for k, v in b.items() if k != "closed_report"} for b in books.book_list(c["tenant_id"])]}

    @app.get("/api/v1/books/{book_id}", tags=["books"])
    def one(book_id: str, c: dict = Depends(need(*WRITERS))):
        b = get_book(c, book_id)
        return {**{k: v for k, v in b.items() if k != "closed_report"}, "entry_count": len(books.entry_list(c["tenant_id"], book_id))}

    @app.put("/api/v1/books/{book_id}/setup", tags=["books"])
    def setup(book_id: str, b: SetupIn, c: dict = Depends(need(*DECIDERS))):
        cur = get_book(c, book_id)
        fields = {}
        if b.opening is not None:
            fields["opening"] = clean_figures(b.opening, SIMPLE, "opening")
        if b.closing is not None:
            fields["closing"] = clean_figures(b.closing, CLOSING_SIMPLE, "closing")
        if not fields or not books.book_update(c["tenant_id"], book_id, "OPEN", **fields):
            raise HTTPException(409, "this period is closed (or nothing to change)")
        audit.append(c["tenant_id"], c["role"], "BOOK_SETUP_CHANGED", book_id=book_id, changed=sorted(fields))
        return {k: v for k, v in get_book(c, book_id).items() if k != "closed_report"}

    @app.post("/api/v1/books/{book_id}/entries", tags=["books"])
    def add_entries(book_id: str, b: AddIn, c: dict = Depends(need(*WRITERS))):
        cur = get_book(c, book_id)
        if cur["status"] != "OPEN":
            raise HTTPException(409, "this period is closed: add the entry to the next period instead")
        recs, errors = [entry_record(e, i) for i, e in enumerate(b.entries, 1)], []
        if b.csv.strip():
            parsed = se.parse_cash_book_csv(b.csv)
            errors += parsed["errors"]
            for i, raw in enumerate(parsed["entries"], len(recs) + 1):
                try:
                    recs.append(entry_record(EntryIn(**{**raw, "receipt": raw.get("receipt") or 0, "payment": raw.get("payment") or 0, "mode": raw.get("mode") or "cash"}), i))
                except Exception as exc:
                    errors.append(f"line {i}: {getattr(exc, 'detail', 'unreadable line')}")
        if not recs:
            raise HTTPException(422, "no usable lines" + (f": {errors[0]}" if errors else ""))
        if len(recs) > BOOK_ENTRIES:
            raise HTTPException(422, f"at most {BOOK_ENTRIES} lines at a time")
        out_of_period = [r for r in recs if not (cur["period_start"] <= r["date"] <= cur["period_end"])]
        if out_of_period:
            raise HTTPException(422, f"{len(out_of_period)} line(s) are dated outside {cur['period_start']} to {cur['period_end']}, for example {out_of_period[0]['date']} '{out_of_period[0]['description'][:40]}'")
        saved = books.entry_add(c["tenant_id"], book_id, recs)
        if saved is None:
            raise HTTPException(409, "this period is closed")
        audit.append(c["tenant_id"], c["role"], "BOOK_ENTRIES_ADDED", book_id=book_id, count=len(saved),
                     total_in=str(sum(Decimal(r["receipt"]) for r in recs)), total_out=str(sum(Decimal(r["payment"]) for r in recs)))
        return {"added": len(saved), "errors": errors, "entries": saved[:200]}

    @app.get("/api/v1/books/{book_id}/entries", tags=["books"])
    def entries(book_id: str, include_void: bool = False, c: dict = Depends(need(*WRITERS))):
        get_book(c, book_id)
        return {"entries": books.entry_list(c["tenant_id"], book_id, include_void=include_void)}

    @app.post("/api/v1/books/{book_id}/entries/{entry_id}/void", tags=["books"])
    def void(book_id: str, entry_id: str, b: VoidIn, c: dict = Depends(need(*DECIDERS))):
        get_book(c, book_id)
        if not books.entry_void(c["tenant_id"], book_id, entry_id, b.reason.strip()):
            raise HTTPException(409, "that line is not active, or this period is closed")
        audit.append(c["tenant_id"], c["role"], "BOOK_ENTRY_VOIDED", book_id=book_id, entry_id=entry_id, reason=b.reason.strip())
        return {"voided": True}

    @app.get("/api/v1/books/{book_id}/report", tags=["books"])
    def report(book_id: str, c: dict = Depends(need(*WRITERS))):
        b = get_book(c, book_id)
        return {"status": b["status"], "report": report_for(c, b)}

    @app.post("/api/v1/books/{book_id}/close", tags=["books"])
    def close(book_id: str, b: CloseIn, c: dict = Depends(need(*DECIDERS))):
        cur = get_book(c, book_id)
        if cur["status"] != "OPEN":
            raise HTTPException(409, "already closed")
        r = report_for(c, cur)
        if r["errors"]:
            raise HTTPException(409, "fix these first: " + "; ".join(r["errors"][:3]))
        if not (r["trial_balance"]["balanced"] and r["statements"]["balance_sheet"]["balanced"] and r["crosscheck"]["agrees"]):
            raise HTTPException(409, "the books do not balance or the independent cross-check disagrees; see the report")
        if (r["counts"]["needs_review"] or r["questions"]) and not b.accept_review:
            raise HTTPException(409, f"{r['counts']['needs_review']} line(s) and {len(r['questions'])} question(s) still need your attention; answer them or close with accept_review")
        if not books.book_update(c["tenant_id"], book_id, "OPEN", status="CLOSED", closed_report=r):
            raise HTTPException(409, "already closed")
        audit.append(c["tenant_id"], c["role"], "BOOK_CLOSED", book_id=book_id, report_sha256=hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest())
        return {"status": "CLOSED", "report": r}

    @app.post("/api/v1/books/{book_id}/rollover", tags=["books"])
    def rollover(book_id: str, b: RolloverIn, c: dict = Depends(need(*DECIDERS))):
        cur = get_book(c, book_id)
        if cur["status"] != "CLOSED" or not cur.get("closed_report"):
            raise HTTPException(409, "close this period first")
        if any(x.get("rolled_from") == book_id for x in books.book_list(c["tenant_id"])):
            raise HTTPException(409, "the next period already exists")
        start = date.fromisoformat(cur["period_end"]) + timedelta(days=1)
        end = b.period_end or date(start.year + 1, start.month, start.day) - timedelta(days=1)
        if end < start or (end - start).days > 400:
            raise HTTPException(422, "the next period must be between 1 and 400 days")
        nxt = books.book_add(c["tenant_id"], {"name": cur["name"], "entity_type": cur["entity_type"], "period_start": start.isoformat(), "period_end": end.isoformat(),
                                              "opening": carry_forward(cur, cur["closed_report"]), "closing": {}, "rolled_from": book_id})
        audit.append(c["tenant_id"], c["role"], "BOOK_ROLLED_OVER", book_id=book_id, next_book_id=nxt["book_id"])
        return nxt

    @app.post("/api/v1/books/{book_id}/tally", tags=["books"])
    def to_tally(book_id: str, b: TallyIn, c: dict = Depends(need(*DECIDERS))):
        stage = getattr(app.state, "tally_stage", None)
        if stage is None:
            raise HTTPException(503, "Tally export is not available on this server")
        cur = get_book(c, book_id)
        r = report_for(c, cur)
        if r["errors"] or not (r["trial_balance"]["balanced"] and r["crosscheck"]["agrees"]):
            raise HTTPException(409, "the books must balance before they are sent to Tally")
        if (r["counts"]["needs_review"] or r["questions"]) and not b.accept_review:
            raise HTTPException(409, "some lines still need review; resolve them or send with accept_review")
        out = se.to_tally(r)
        staged = []
        if out["ledgers"]:
            staged.append({"what": "ledgers", **stage(c, "masters", b.company, tallybooks.masters_xml(b.company, out["ledgers"]),
                                                       {"count": len(out["ledgers"]), "items": [{"name": l.name, "parent": l.parent} for l in out["ledgers"]]})})
        vs = out["vouchers"]
        for i in range(0, len(vs), TALLY_CHUNK):
            chunk, bid = vs[i:i + TALLY_CHUNK], str(uuid.uuid4())
            summary = {"count": len(chunk), "total": str(sum((max(v.total_dr(), v.total_cr()) for v in chunk), Decimal(0))),
                       "items": [{"vtype": v.vtype, "date": v.date.isoformat(), "party": v.party, "amount": str(max(v.total_dr(), v.total_cr())), "flags": list(v.flags)} for v in chunk[:100]]}
            staged.append({"what": f"vouchers {i + 1}-{i + len(chunk)}", **stage(c, "vouchers", b.company,
                           tallybooks.voucher_xml(b.company, chunk, remote_id_prefix=f"ts-{bid}"), summary, batch_id=bid)})
        audit.append(c["tenant_id"], c["role"], "BOOK_TALLY_STAGED", book_id=book_id, batches=[s["batch_id"] for s in staged])
        return {"staged": staged, "note": "Review and approve these batches in the Tally Assistant; the opening balances go in as a journal voucher."}
