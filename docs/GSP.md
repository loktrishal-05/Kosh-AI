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
* **Sessions are held in one process's memory.** On Vercel's serverless functions a session will not survive between requests; run live mode on a long-running host (`render.yaml` exists) or add a session store first.
* The mock approval OTP (`/hitl/request-otp`) is still echoed in the response; before real use it must be delivered by SMS/WhatsApp.

## Going live (what a person has to do)
1. Contract a GSP and get **sandbox** credentials (client id, client secret, GSTN's public key/certificate, base URL and the route names for authenticate and returns).
2. Set on the server: `TAXSETU_GSP_BASE_URL`, `TAXSETU_GSP_CLIENT_ID`, `TAXSETU_GSP_CLIENT_SECRET`, `TAXSETU_GSP_PUBLIC_KEY` (PEM text or a file path); optionally `TAXSETU_GSP_AUTH_PATH`, `TAXSETU_GSP_RETURN_PATH` (use `{kind}`), `TAXSETU_GSP_IP_USR`.
3. Run a GSTR-3B save against the GSP's **sandbox** GSTIN, compare the reply shapes with `FakeGstn` in the test file and adjust.
4. Only then move to production credentials.
