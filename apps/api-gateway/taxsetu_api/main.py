"""FastAPI edge: REST + WhatsApp webhook over the deterministic engine and the HITL gate (report s3.4)."""
import hashlib
import hmac
import os
from datetime import date, datetime
from decimal import Decimal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from taxsetu_engine import ewb, gst, itr, recon, refund

from fastapi import encoders

from . import auth
from .hitl import HitlGate
from .portal import PortalError

# FastAPI encodes Decimal as a JSON float/int by default (180.00 -> 180.0), which breaks exact-money guarantees.
# Emit every Decimal as a plain-decimal string instead.
encoders.ENCODERS_BY_TYPE[Decimal] = lambda x: format(x, "f")
encoders.encoders_by_class_tuples = encoders.generate_encoders_by_class_tuples(encoders.ENCODERS_BY_TYPE)


def create_app(secret: bytes | None = None, wa_secret: bytes | None = None) -> FastAPI:
    secret = secret or os.environ.get("HITL_SIGNING_SECRET", "dev-only-change-me").encode()
    wa_secret = wa_secret or os.environ.get("WHATSAPP_APP_SECRET", "").encode()
    gate = HitlGate(secret)
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

    @app.get("/health")
    def health():
        return {"ok": True, "audit_chain_valid": gate.audit.verify()}

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
        verification_mode: str = Field(default="EVC_OTP", pattern="^(EVC_OTP|AADHAAR_OTP|DSC)$")
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
        return {"valid": gate.audit.verify(), "events": gate.audit.events(c["tenant_id"])}

    return app


app = create_app()
