"""FastAPI edge: REST + WhatsApp webhook over the deterministic engine and the HITL gate (report s3.4)."""
import hashlib
import hmac
import os
from datetime import date, datetime
from decimal import Decimal

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from taxsetu_engine import ewb, gst, itr, recon, refund

from fastapi import encoders

from . import auth, demo, store
from .hitl import HitlGate
from .portal import PortalError

# FastAPI encodes Decimal as a JSON float/int by default (180.00 -> 180.0), which breaks exact-money guarantees.
# Emit every Decimal as a plain-decimal string instead.
encoders.ENCODERS_BY_TYPE[Decimal] = lambda x: format(x, "f")
encoders.encoders_by_class_tuples = encoders.generate_encoders_by_class_tuples(encoders.ENCODERS_BY_TYPE)


def create_app(secret: bytes | None = None, wa_secret: bytes | None = None) -> FastAPI:
    secret = secret or os.environ.get("HITL_SIGNING_SECRET", "dev-only-change-me").encode()
    wa_secret = wa_secret or os.environ.get("WHATSAPP_APP_SECRET", "").encode()
    drafts, audit = store.from_env()      # Postgres (RLS) when DATABASE_URL_APP is set, else in-memory
    if drafts is not None and secret == b"dev-only-change-me":
        raise RuntimeError("refusing to run on Postgres with the default HITL_SIGNING_SECRET: tokens would be forgeable")
    gate = HitlGate(secret, audit=audit, drafts=drafts)
    app = FastAPI(title="TaxSetu AI API", version="0.1.0")
    app.state.gate, app.state.seen_wamids = gate, set()

    def who(authorization: str = Header(default="")) -> dict:
        try:
            return auth.decode(authorization.removeprefix("Bearer ").strip(), secret)
        except ValueError:
            raise HTTPException(401, "invalid or missing token")

    def need(*roles):
        def dep(c: dict = Depends(who)) -> dict:
            if c["role"] not in roles:
                raise HTTPException(403, f"role {c['role']} not permitted")
            return c
        return dep

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing():
        return (Path(__file__).parent / "landing.html").read_text(encoding="utf-8")

    @app.get("/api/v1/demo/storyline", tags=["sandbox"])
    def demo_storyline():
        """Runs all five agents + the OTP gate on fake data in one stateless request (fresh in-memory gate per call)."""
        return demo.storyline()

    class DevTokenIn(BaseModel):
        tenant_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
        role: str = Field(default="OWNER", pattern="^(OWNER|CA|CLERK|EMPLOYEE)$")

    @app.post("/api/v1/auth/dev-token", tags=["auth"])
    def dev_token(b: DevTokenIn, x_admin_key: str = Header(default="")):
        """Stopgap login until WhatsApp/mobile OTP exists: whoever holds TAXSETU_ADMIN_KEY can mint a 12 h token. Disabled when unset."""
        key = os.environ.get("TAXSETU_ADMIN_KEY", "")
        if len(key) < 24 or not hmac.compare_digest(x_admin_key.encode(), key.encode()):
            raise HTTPException(401, "admin key required")
        return {"token": auth.encode({"tenant_id": b.tenant_id, "role": b.role}, secret, ttl_s=12 * 3600), "expires_in_s": 12 * 3600}

    @app.get("/health")
    def health():
        if drafts is None:
            return {"ok": True, "store": "memory", "audit_chain_valid": gate.audit.verify()}
        try:      # Postgres chains are per tenant (verified via /api/v1/audit); here prove we connect as the RLS-bound role, not a bypass role
            with drafts.pg.tx("00000000-0000-0000-0000-000000000000") as c:
                user, bypass = c.execute("SELECT current_user, (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)").fetchone()
        except Exception as e:      # class name only: connection errors can carry the DSN
            return {"ok": False, "store": "postgres", "error": type(e).__name__}
        return {"ok": not bypass, "store": "postgres", "db_role": user, "bypass_rls": bypass}

    # ---- WhatsApp webhook: HMAC verified, idempotent on wamid --------------------------------------------------
    @app.post("/api/v1/webhooks/whatsapp")
    async def whatsapp(request: Request, x_hub_signature_256: str = Header(default="")):
        raw = await request.body()
        good = "sha256=" + hmac.new(wa_secret, raw, hashlib.sha256).hexdigest()
        if not wa_secret or not hmac.compare_digest(x_hub_signature_256, good):
            raise HTTPException(401, "bad signature")
        queued = 0
        for entry in (await request.json()).get("entry", []):
            for ch in entry.get("changes", []):
                for m in ch.get("value", {}).get("messages", []):
                    if m.get("id") not in app.state.seen_wamids:
                        app.state.seen_wamids.add(m.get("id"))
                        queued += 1       # ponytail: push to Redis Streams for the agents once the queue layer exists
        return {"status": "queued", "new_messages": queued}

    # ---- GSTR-2B reconciliation --------------------------------------------------------------------------------
    class InvIn(BaseModel):
        gstin: str
        inv_no: str
        taxable: Decimal
        tax: Decimal
        pos: str = ""

    class ReconIn(BaseModel):
        return_period: str
        purchases: list[InvIn]
        gstr2b: list[InvIn]

    @app.post("/api/v1/gst/{gstin}/reconcile-2b")
    def reconcile(gstin: str, body: ReconIn, c: dict = Depends(need("OWNER", "CA"))):
        if not gst.is_valid_gstin(gstin):
            raise HTTPException(422, "invalid GSTIN checksum")
        mk = lambda x: recon.Inv(x.gstin, x.inv_no, x.taxable, x.tax, x.pos)
        out = recon.reconcile([mk(p) for p in body.purchases], [mk(g) for g in body.gstr2b])
        rows = [{"inv_no": r["invoice"].inv_no, "gstin": r["invoice"].gstin, "status": r["status"]} for r in out["rows"]]
        gate.audit.append(c["tenant_id"], c["role"], "RECON_COMPLETED", period=body.return_period, rows=len(rows))
        return {"rows": rows, "eligible_itc": out["eligible_itc"], "deferred_itc": out["deferred_itc"],
                "to_chase": [i.inv_no for i in out["chase"]]}

    # ---- e-Way Bill: generate (staged, 1-tap) or defend MOV-07 -------------------------------------------------
    class EwbIn(BaseModel):
        mode: str = Field(pattern="^(GENERATE_EWB|DEFEND_MOV07)$")
        gstin: str
        vehicle_no: str
        consignment_value: Decimal = Decimal(0)
        distance_km: Decimal = Decimal(0)
        interstate: bool = True
        defect: str = "OTHER"
        declared_vehicle: str = ""
        actual_vehicle: str = ""
        valid_invoice_on_file: bool = False
        tax_payable: Decimal = Decimal(0)

    @app.post("/api/v1/ewb/generate-or-defend")
    def ewb_route(b: EwbIn, c: dict = Depends(need("OWNER", "CLERK", "DRIVER"))):
        if b.mode == "GENERATE_EWB":
            if not gst.is_valid_gstin(b.gstin):
                raise HTTPException(422, "invalid GSTIN checksum")
            if not ewb.ewb_required(b.consignment_value, b.interstate):
                return {"required": False}
            valid = ewb.ewb_valid_until(datetime.now(), b.distance_km)
            d = gate.agent_tools.stage(c["tenant_id"], "EWB", {"gstin": b.gstin, "vehicle_no": b.vehicle_no,
                                                              "distance_km": str(b.distance_km), "valid_until": valid.isoformat()})
            return {"required": True, "valid_until": valid.isoformat(), "alert_at": ewb.expiry_alert_time(valid).isoformat(), **d}
        v = ewb.classify_mov07(b.defect, b.valid_invoice_on_file, b.tax_payable,
                               declared=b.declared_vehicle, actual=b.actual_vehicle)
        letter = (f"Reply to MOV-07: defect '{b.defect}'. Valid tax invoice on file; tax fully paid. "
                  + ("Relief sought under CBIC Circular No. 64/38/2018-GST: penalty limited to Rs 1,000 under Section 125."
                     if v.circular_64_38_applies else "Circular 64/38/2018-GST is NOT cited: " + v.reason + "."))
        return {"circular_64_38_applies": v.circular_64_38_applies, "penalty": v.penalty, "basis": v.basis,
                "reason": v.reason, "draft_reply": letter}

    # ---- ITR compute-and-stage -----------------------------------------------------------------------------------
    class ItrIn(BaseModel):
        assessment_year: str = "2026-27"
        entity: str = "INDIVIDUAL"
        digital_turnover: Decimal = Decimal(0)
        cash_turnover: Decimal = Decimal(0)
        other_income: Decimal = Decimal(0)
        stcg_111a: Decimal = Decimal(0)
        ltcg_112a: Decimal = Decimal(0)
        director: bool = False

    @app.post("/api/v1/itr/{pan}/compute-and-stage")
    def itr_route(pan: str, b: ItrIn, c: dict = Depends(need("OWNER", "CA", "EMPLOYEE"))):
        if not gst.is_valid_pan(pan):
            raise HTTPException(422, "invalid PAN")
        pres = itr.presumptive_44ad(b.digital_turnover, b.cash_turnover) if (b.digital_turnover + b.cash_turnover) else None
        biz_income = pres.income if pres and pres.eligible else Decimal(0)
        total = biz_income + b.other_income + b.stcg_111a + b.ltcg_112a
        form, why = itr.route_itr(itr.Taxpayer(
            entity=b.entity, total_income=total, business_income=pres is not None, presumptive=bool(pres and pres.eligible),
            stcg_111a=b.stcg_111a, ltcg_112a=b.ltcg_112a, director=b.director))
        regimes = itr.compare_regimes(total, salaried=False)
        d = gate.agent_tools.stage(c["tenant_id"], "ITR", {"pan": pan, "assessment_year": b.assessment_year, "form": form,
                                                           "total_income": str(total), "regime": regimes["best"],
                                                           "tax": str(regimes[regimes["best"].lower() + "_tax"])})
        return {"form": form, "reasons": why, "presumptive": pres and {"income": pres.income, "eligible": pres.eligible,
                "cash_ratio_pct": pres.cash_ratio_pct, "reason": pres.reason}, "regimes": regimes, **d}

    @app.get("/api/v1/refund-pathway")
    def refund_route(ay_start_year: int, return_filed: bool = False, today: date | None = None,
                     _: dict = Depends(need("OWNER", "CA", "EMPLOYEE"))):
        a = refund.pick_refund_pathway(ay_start_year, today or date.today(), return_filed=return_filed)
        return {"pathway": a.pathway, "itr_u_allowed": a.itr_u_allowed, "deadline": a.deadline, "notes": a.notes}

    # ---- HITL (human only) ---------------------------------------------------------------------------------------
    class AuthIn(BaseModel):
        draft_id: str
        payload_sha256: str
        verification_mode: str = Field(default="EVC_OTP", pattern="^(EVC_OTP|AADHAAR_OTP|CLASS3_DSC)$")
        otp_or_signature: str

    @app.post("/api/v1/hitl/request-otp/{draft_id}")
    def request_otp(draft_id: str, c: dict = Depends(need("OWNER", "EMPLOYEE", "CA"))):
        try:
            otp = gate.request_otp(c["tenant_id"], draft_id)
        except PortalError as e:
            raise HTTPException(404, str(e))
        return {"sent": True, "mock_otp": otp}   # ponytail: mock mode echoes the OTP; live mode must never return it

    @app.post("/api/v1/hitl/authorize-filing")
    def authorize(b: AuthIn, c: dict = Depends(need("OWNER", "EMPLOYEE"))):    # CA cannot self-sign for the client
        try:
            return gate.authorize(c["tenant_id"], b.draft_id, b.payload_sha256, b.otp_or_signature, c["role"], b.verification_mode)
        except PortalError as e:
            raise HTTPException(409, str(e))

    @app.get("/api/v1/audit")
    def audit_log(c: dict = Depends(need("OWNER", "CA"))):
        return {"valid": gate.audit.verify(c["tenant_id"]), "events": gate.audit.events(c["tenant_id"])}

    return app


app = create_app()
