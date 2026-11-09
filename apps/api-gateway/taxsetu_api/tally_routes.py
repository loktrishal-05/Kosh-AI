"""Tally autopilot routes. Three audiences:
  /sandbox/*  anonymous, stateless demo of the classifier and the starter chart of accounts (nothing is stored)
  /tally/*    authenticated owners/CAs: draft, stage a batch, approve the exact bytes, pair a bridge
  /bridge/*   the program on the customer PC: fetch approved batches, report what Tally said
Nothing reaches Tally unless a human approved the batch's SHA-256, and the bridge re-verifies a signature before posting."""
import hashlib
import hmac
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from taxsetu_engine import tally_bank, tally_classify, tally_coa, tallybooks
from taxsetu_engine.tally_models import BookContext, draft_from_dict, draft_to_dict

from . import auth

PAIR_TTL_S, BRIDGE_TTL_S = 15 * 60, 90 * 24 * 3600
MAX_DRAFTS = 500


def signing_key(secret: bytes, bridge_id: str) -> str:
    """Per-bridge HMAC key derived from the server secret: nothing extra to store, revoked bridges simply stop being served."""
    return hmac.new(secret, b"bridge-sign:" + bridge_id.encode(), hashlib.sha256).hexdigest()


def sign(secret: bytes, bridge_id: str, sha256_hex: str) -> str:
    return hmac.new(signing_key(secret, bridge_id).encode(), sha256_hex.encode(), hashlib.sha256).hexdigest()


def _inr(x: Decimal) -> str:
    return f"Rs {x:,.2f}"


def explain(d) -> str:
    """One plain sentence, no accounting jargon, for people who have never used Tally."""
    total = max(d.total_dr(), d.total_cr())
    dr = ", ".join(l.ledger for l in d.lines if l.side == "Dr")
    cr = ", ".join(l.ledger for l in d.lines if l.side == "Cr")
    who = f" {d.party}" if d.party else ""
    return {
        "Payment": f"You paid {_inr(total)}{(' to' + who) if who else ''}. Money leaves {cr} and is recorded under {dr}.",
        "Receipt": f"You received {_inr(total)}{(' from' + who) if who else ''}. Money comes into {dr} and is recorded against {cr}.",
        "Sales": f"You sold to{who or ' a customer'} for {_inr(total)} including GST. {dr} owes you; {cr} are recorded as income and GST payable.",
        "Purchase": f"You bought from{who or ' a supplier'} for {_inr(total)} including GST. {cr} is what you owe; {dr} are recorded as cost and GST you can claim back.",
        "Contra": f"You moved {_inr(total)} between your own cash and bank: from {cr} to {dr}.",
    }.get(d.vtype, f"A journal adjustment of {_inr(total)}: debits {dr}, credits {cr}.")


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    today: date | None = None
    state_code: str = Field(default="", max_length=2)
    bank_ledger: str = Field(default="Bank Account", max_length=99)
    cash_ledger: str = Field(default="Cash", max_length=99)


class CsvIn(BaseModel):
    csv: str = Field(min_length=1, max_length=600_000)
    state_code: str = Field(default="", max_length=2)
    bank_ledger: str = Field(default="Bank Account", max_length=99)
    cash_ledger: str = Field(default="Cash", max_length=99)


class BatchIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    drafts: list[dict] = Field(min_length=1, max_length=MAX_DRAFTS)
    allow_suspense: bool = False


class SetupIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    business_type: str = Field(pattern="^(trader|service|manufacturer)$")
    state_code: str = Field(pattern=r"^\d{2}$")


class ApproveIn(BaseModel):
    payload_sha256: str = Field(min_length=64, max_length=64)


class AliasIn(BaseModel):
    party: str = Field(min_length=1, max_length=60)
    ledger: str = Field(min_length=1, max_length=99)


class BridgeIn(BaseModel):
    company: str = Field(min_length=1, max_length=120)


class PairIn(BaseModel):
    code: str = Field(min_length=10, max_length=2000)
    host: str = Field(default="", max_length=120)


class AckIn(BaseModel):
    id: str
    ok: bool
    created: int = 0
    altered: int = 0
    errors: list[str] = Field(default_factory=list, max_length=50)
    response: str = Field(default="", max_length=4000)


class LedgersIn(BaseModel):
    ledgers: list[dict] = Field(max_length=5000)


def _ctx(tally, tenant: str | None, company: str, state_code: str, bank_ledger: str, cash_ledger: str) -> BookContext:
    synced = tally.ledgers(tenant) if tenant else []
    return BookContext(company=company, state_code=state_code, bank_ledger=bank_ledger, cash_ledger=cash_ledger,
                       aliases=tally.aliases(tenant) if tenant else {}, known_ledgers={l["name"] for l in synced})


def _entry(text: str, today: date | None, ctx: BookContext) -> dict:
    r = tally_classify.draft_from_text(text, today or date.today(), ctx)
    d = r["draft"]
    out = {"draft": draft_to_dict(d) if d else None, "questions": r["questions"], "flags": r["flags"],
           "interpretation": r["interpretation"]}
    if d:
        out["plain"] = explain(d)
        out["xml_preview"] = tallybooks.voucher_xml(ctx.company or "Your Company", [d])
    return out


def _statement(csv: str, ctx: BookContext) -> dict:
    parsed = tally_bank.parse_statement_csv(csv)
    drafts = tally_bank.to_drafts(parsed["txns"], ctx)
    return {"errors": parsed["errors"], "skipped": parsed["skipped"], "summary": tally_bank.summary(drafts),
            "drafts": [{**draft_to_dict(d), "plain": explain(d)} for d in drafts]}


def mount(app, *, secret: bytes, gate, tally, who, need) -> None:
    audit = gate.audit

    # ---- sandbox: anonymous, stateless -----------------------------------------------------------------------
    @app.get("/api/v1/tally/sandbox/starter-pack", tags=["tally-sandbox"])
    def sandbox_pack(business_type: str = "trader", state_code: str = "29"):
        try:
            pack = tally_coa.starter_pack(business_type, state_code)
        except ValueError as e:
            raise HTTPException(422, str(e))
        why = tally_coa.plain_explanations()
        return {"ledgers": [{"name": l.name, "parent": l.parent, "duty_head": l.gst_duty_head, "meaning": why.get(l.name, "")} for l in pack],
                "xml": tallybooks.masters_xml("Your Company", pack)}

    @app.post("/api/v1/tally/sandbox/entry", tags=["tally-sandbox"])
    def sandbox_entry(b: TextIn):
        return _entry(b.text, b.today, _ctx(tally, None, "Your Company", b.state_code, b.bank_ledger, b.cash_ledger))

    @app.post("/api/v1/tally/sandbox/bank-statement", tags=["tally-sandbox"])
    def sandbox_statement(b: CsvIn):
        return _statement(b.csv, _ctx(tally, None, "Your Company", b.state_code, b.bank_ledger, b.cash_ledger))

    @app.post("/api/v1/tally/sandbox/voucher-xml", tags=["tally-sandbox"])
    def sandbox_xml(b: BatchIn):
        """Stateless: turn reviewed drafts into the Tally import file so a demo user can download it (nothing is stored or sent)."""
        drafts = []
        for i, raw in enumerate(b.drafts):
            try:
                d = draft_from_dict(raw)
            except (ValueError, KeyError, TypeError, InvalidOperation) as e:
                raise HTTPException(422, f"entry {i + 1}: {e}")
            if not d.balanced():
                raise HTTPException(422, f"entry {i + 1}: debits and credits do not match")
            drafts.append(d)
        return {"xml": tallybooks.voucher_xml(b.company, drafts), "count": len(drafts)}

    # ---- authenticated: draft -> stage -> approve -------------------------------------------------------------
    DRAFTERS = ("OWNER", "CA", "CLERK", "EMPLOYEE")

    @app.post("/api/v1/tally/entry", tags=["tally"])
    def entry(b: TextIn, c: dict = Depends(need(*DRAFTERS))):
        return _entry(b.text, b.today, _ctx(tally, c["tenant_id"], "", b.state_code, b.bank_ledger, b.cash_ledger))

    @app.post("/api/v1/tally/bank-statement", tags=["tally"])
    def statement(b: CsvIn, c: dict = Depends(need(*DRAFTERS))):
        return _statement(b.csv, _ctx(tally, c["tenant_id"], "", b.state_code, b.bank_ledger, b.cash_ledger))

    def stage(c: dict, kind: str, company: str, xml: str, summary: dict) -> dict:
        sha = hashlib.sha256(xml.encode("utf-8")).hexdigest()
        item = tally.outbox_add(c["tenant_id"], {"kind": kind, "company": company, "xml": xml, "sha256": sha, "summary": summary})
        audit.append(c["tenant_id"], c["role"], "TALLY_BATCH_STAGED", batch_id=item["batch_id"], payload_sha256=sha, kind=kind)
        return {"batch_id": item["batch_id"], "payload_sha256": sha, "status": item["status"], "summary": summary}

    @app.post("/api/v1/tally/batches", tags=["tally"])
    def stage_batch(b: BatchIn, c: dict = Depends(need(*DRAFTERS))):
        drafts = []
        for i, raw in enumerate(b.drafts):
            try:
                d = draft_from_dict(raw)
            except (ValueError, KeyError, TypeError, InvalidOperation) as e:
                raise HTTPException(422, f"entry {i + 1}: {e}")
            if not d.balanced():
                raise HTTPException(422, f"entry {i + 1}: debits and credits do not match")
            if not b.allow_suspense and any(l.ledger == "Suspense A/c" for l in d.lines):
                raise HTTPException(422, f"entry {i + 1}: pick a real ledger instead of Suspense A/c (or set allow_suspense)")
            drafts.append(d)
        summary = {"count": len(drafts), "total": str(sum((max(d.total_dr(), d.total_cr()) for d in drafts), Decimal(0))),
                   "items": [{"vtype": d.vtype, "date": d.date.isoformat(), "party": d.party,
                              "amount": str(max(d.total_dr(), d.total_cr())), "flags": list(d.flags)} for d in drafts]}
        return stage(c, "vouchers", b.company, tallybooks.voucher_xml(b.company, drafts), summary)

    @app.post("/api/v1/tally/setup", tags=["tally"])
    def setup(b: SetupIn, c: dict = Depends(need("OWNER", "CA"))):
        have = {l["name"] for l in tally.ledgers(c["tenant_id"])}
        todo = [l for l in tally_coa.starter_pack(b.business_type, b.state_code) if l.name not in have]
        if not todo:
            return {"nothing_to_do": True}
        summary = {"count": len(todo), "items": [{"name": l.name, "parent": l.parent} for l in todo]}
        return stage(c, "masters", b.company, tallybooks.masters_xml(b.company, todo), summary)

    @app.get("/api/v1/tally/batches", tags=["tally"])
    def batches(c: dict = Depends(need("OWNER", "CA", "CLERK", "EMPLOYEE"))):
        return {"batches": [{k: v for k, v in i.items() if k != "xml"} for i in tally.outbox_list(c["tenant_id"])]}

    @app.get("/api/v1/tally/batches/{batch_id}", tags=["tally"])
    def batch(batch_id: str, c: dict = Depends(need("OWNER", "CA", "CLERK", "EMPLOYEE"))):
        i = tally.outbox_get(c["tenant_id"], batch_id)
        if not i:
            raise HTTPException(404, "batch not found")
        return i

    @app.post("/api/v1/tally/batches/{batch_id}/approve", tags=["tally"])
    def approve(batch_id: str, b: ApproveIn, c: dict = Depends(need("OWNER", "CA"))):
        i = tally.outbox_get(c["tenant_id"], batch_id)
        if not i:
            raise HTTPException(404, "batch not found")
        if not hmac.compare_digest(b.payload_sha256, i["sha256"]):
            raise HTTPException(409, "the batch changed since you reviewed it")
        if not tally.set_status(c["tenant_id"], batch_id, "PENDING_APPROVAL", "APPROVED", approved_by=c["role"]):
            raise HTTPException(409, "this batch was already decided")
        audit.append(c["tenant_id"], c["role"], "TALLY_BATCH_APPROVED", batch_id=batch_id, payload_sha256=i["sha256"])
        return {"status": "APPROVED", "note": "Your Tally bridge will post it within about a minute."}

    @app.post("/api/v1/tally/batches/{batch_id}/reject", tags=["tally"])
    def reject(batch_id: str, c: dict = Depends(need("OWNER", "CA"))):
        if not tally.set_status(c["tenant_id"], batch_id, "PENDING_APPROVAL", "REJECTED", approved_by=c["role"]):
            raise HTTPException(409, "batch not found or already decided")
        audit.append(c["tenant_id"], c["role"], "TALLY_BATCH_REJECTED", batch_id=batch_id)
        return {"status": "REJECTED"}

    @app.post("/api/v1/tally/aliases", tags=["tally"])
    def alias(b: AliasIn, c: dict = Depends(need("OWNER", "CA", "CLERK"))):
        ctx = BookContext()
        tally_classify.learn_alias(ctx, b.party, b.ledger)
        if not ctx.aliases:
            raise HTTPException(422, "that ledger name is not allowed")
        (k, v), = ctx.aliases.items()
        tally.alias_put(c["tenant_id"], k, v)
        audit.append(c["tenant_id"], c["role"], "ALIAS_LEARNED", alias=k, ledger=v)
        return {"learned": {k: v}}

    @app.get("/api/v1/tally/ledgers", tags=["tally"])
    def ledgers(c: dict = Depends(need("OWNER", "CA", "CLERK", "EMPLOYEE"))):
        return {"ledgers": tally.ledgers(c["tenant_id"])}

    # ---- bridge lifecycle (owner side) ----------------------------------------------------------------------------
    @app.post("/api/v1/tally/bridges", tags=["tally-bridge"])
    def new_bridge(b: BridgeIn, c: dict = Depends(need("OWNER", "CA"))):
        br = tally.bridge_add(c["tenant_id"], b.company)
        code = auth.encode({"tenant_id": c["tenant_id"], "role": "PAIR", "bridge_id": br["bridge_id"]}, secret, ttl_s=PAIR_TTL_S)
        return {"bridge_id": br["bridge_id"], "pairing_code": code, "expires_in_s": PAIR_TTL_S}

    @app.get("/api/v1/tally/bridges", tags=["tally-bridge"])
    def bridges(c: dict = Depends(need("OWNER", "CA"))):
        return {"bridges": tally.bridge_list(c["tenant_id"])}

    @app.delete("/api/v1/tally/bridges/{bridge_id}", tags=["tally-bridge"])
    def revoke(bridge_id: str, c: dict = Depends(need("OWNER", "CA"))):
        if not tally.bridge_update(c["tenant_id"], bridge_id, revoked=True):
            raise HTTPException(404, "bridge not found")
        audit.append(c["tenant_id"], c["role"], "BRIDGE_REVOKED", bridge_id=bridge_id)
        return {"revoked": True}

    # ---- bridge side (the program on the customer PC) ---------------------------------------------------------------
    @app.post("/api/v1/tally/bridge/pair", tags=["tally-bridge"])
    def pair(b: PairIn):
        try:
            claims = auth.decode(b.code, secret)
        except ValueError:
            raise HTTPException(401, "pairing code is invalid or expired")
        if claims["role"] != "PAIR" or not claims.get("bridge_id"):
            raise HTTPException(401, "pairing code is invalid or expired")
        tenant, bid = claims["tenant_id"], claims["bridge_id"]
        br = tally.bridge_get(tenant, bid)
        if not br or br["revoked"] or not tally.bridge_update(tenant, bid, expect_paired=False, paired=True, host=b.host):
            raise HTTPException(409, "this pairing code was already used")      # single use
        audit.append(tenant, "BRIDGE", "BRIDGE_PAIRED", bridge_id=bid, host=b.host)
        token = auth.encode({"tenant_id": tenant, "role": "BRIDGE", "bridge_id": bid}, secret, ttl_s=BRIDGE_TTL_S)
        return {"bridge_token": token, "signing_key": signing_key(secret, bid), "company": br["company"]}

    def bridge_who(c: dict = Depends(need("BRIDGE"))) -> dict:
        br = tally.bridge_get(c["tenant_id"], c.get("bridge_id", ""))
        if not br or br["revoked"] or not br["paired"]:
            raise HTTPException(401, "bridge is not active")
        from datetime import datetime, timezone
        tally.bridge_update(c["tenant_id"], br["bridge_id"], last_seen=datetime.now(timezone.utc).isoformat())
        return {**c, "company": br["company"]}

    @app.get("/api/v1/tally/bridge/pending", tags=["tally-bridge"])
    def pending(c: dict = Depends(bridge_who)):
        rows = [i for i in tally.outbox_list(c["tenant_id"], "APPROVED") if i["company"] == c["company"]][:20]
        return {"items": [{"id": i["batch_id"], "kind": i["kind"], "xml": i["xml"], "sha256": i["sha256"],
                           "sig": sign(secret, c["bridge_id"], i["sha256"])} for i in rows]}

    @app.post("/api/v1/tally/bridge/ack", tags=["tally-bridge"])
    def ack(b: AckIn, c: dict = Depends(bridge_who)):
        new = "POSTED" if b.ok else "FAILED"
        res = {"ok": b.ok, "created": b.created, "altered": b.altered, "errors": [e[:300] for e in b.errors], "response": b.response[:2000]}
        if not tally.set_status(c["tenant_id"], b.id, "APPROVED", new, ack=res):
            cur = tally.outbox_get(c["tenant_id"], b.id)
            if cur and cur["status"] == new:
                return {"status": new}                      # retried ack: idempotent
            raise HTTPException(409, "batch is not waiting for an acknowledgement")
        audit.append(c["tenant_id"], "BRIDGE", f"TALLY_BATCH_{new}", batch_id=b.id, created=b.created, altered=b.altered)
        return {"status": new}

    @app.post("/api/v1/tally/bridge/ledgers", tags=["tally-bridge"])
    def sync_ledgers(b: LedgersIn, c: dict = Depends(bridge_who)):
        clean = [{"name": str(l["name"])[:99], "parent": str(l.get("parent", ""))[:99], "gstin": str(l.get("gstin", ""))[:15]}
                 for l in b.ledgers if isinstance(l, dict) and l.get("name")]
        tally.ledgers_replace(c["tenant_id"], clean)
        return {"synced": len(clean)}
