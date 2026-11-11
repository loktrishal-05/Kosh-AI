# Live GST portal access (GSP) and income tax (ERI)

Code: `apps/api-gateway/taxsetu_api/gsp_live.py`, routes in `main.py` (`/api/v1/gsp/*`), tests in `tests/e2e-demo/test_gsp_live.py`.

## What exists
* **GST, through a GSP (GST Suvidha Provider).** A taxpayer logs in to the GST portal (GSTN sends the OTP to their own registered mobile), the server keeps that session in memory,
  and an approved GSTR-1 / GSTR-3B draft is **saved** at the portal (`RETSAVE`). The reply is checked (AES envelope, HMAC) and returned as `ack_type: RETSAVE, final: false`.
* **It never files.** Filing a GST return needs the taxpayer's EVC (or a DSC). The client has no filing call at all; the gate reports `SAVED_AT_PORTAL_AWAITING_EVC`, leaves the
  draft as `DRAFT_STAGED` and audits `filed: false`. The taxpayer files on the portal (or through the DSC bridge).
* **Same human gate.** The provider still refuses without the gate's approval token bound to the exact payload hash; sessions are per tenant and GSTIN, so one tenant cannot ride another's session.
* **Off unless configured.** With no credentials the app runs on the mock exactly as before and `/api/v1/gsp/status` says `live: false`.

## What does not exist, and why
* **Income tax (ERI).** The ERI API specification and credentials are issued only after registering as an e-Return Intermediary and passing the department's data-transmission test; it is not public,
  so no client was written (guessing it would be worse than nothing). ITR and e-way bills stay on the mock and are marked `simulated: true`.
* **Verification against a real GSP.** The client was tested against a protocol **simulator** that plays GSTN's side (RSA-wrapped app key, OTP, session key, AES-256 envelope, HMAC), written from what
  GSP vendors publish. Field names and routes differ slightly between GSPs; routes and header names are configurable, but **compatibility with a real GSP is unproven** until it is run against a sandbox.
* **Sessions** are kept in Postgres (table `gsp_sessions`, migration 0007, RLS by tenant, sealed with Fernet under a key derived from `HITL_SIGNING_SECRET`), so they survive serverless invocations; without a database they stay in one process's memory. **Apply migration 0007 to Neon before switching live mode on.**
* **Approval OTP delivery.** In live mode `/hitl/request-otp` never returns the OTP. Set `TAXSETU_OTP_WEBHOOK_URL` (https) and optionally `TAXSETU_OTP_WEBHOOK_TOKEN`: the server POSTs `{tenant_id, draft_id, otp}` to it and your SMS/WhatsApp gateway texts the owner. No webhook in live mode means a 503, not an echo. The demo/mock mode (no GSP configured, no webhook) still echoes the OTP.

## Going live (what a person has to do)
1. Contract a GSP and get **sandbox** credentials (client id, client secret, GSTN's public key/certificate, base URL and the route names for authenticate and returns).
2. Set on the server: `TAXSETU_GSP_BASE_URL`, `TAXSETU_GSP_CLIENT_ID`, `TAXSETU_GSP_CLIENT_SECRET`, `TAXSETU_GSP_PUBLIC_KEY` (PEM text or a file path); optionally `TAXSETU_GSP_AUTH_PATH`, `TAXSETU_GSP_RETURN_PATH` (use `{kind}`), `TAXSETU_GSP_IP_USR`.
3. Run a GSTR-3B save against the GSP's **sandbox** GSTIN, compare the reply shapes with `FakeGstn` in the test file and adjust.
4. Only then move to production credentials.

## Sandbox run
With sandbox credentials set (step 2 above): `python scripts/gsp_sandbox_check.py <SANDBOX_GSTIN> <portal_user> <MMYYYY>`. It requests the OTP, asks you to type it, saves a minimal GSTR-3B **draft** (never files) and prints OK / FAIL / DIFF per step plus the reply's keys. Fix route differences with `TAXSETU_GSP_AUTH_PATH` / `TAXSETU_GSP_RETURN_PATH`; header or reply-field differences need a small edit in `gsp_live.py` (`GspConfig.header_names`, `LivePortalProvider.file`).
