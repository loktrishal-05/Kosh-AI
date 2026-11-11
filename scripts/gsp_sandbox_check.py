"""Run once against a GSP SANDBOX to learn whether this client matches the real GSP. Saves a tiny GSTR-3B draft for a SANDBOX GSTIN (never files) and reports what differs.
Usage: TAXSETU_GSP_BASE_URL=... TAXSETU_GSP_CLIENT_ID=... TAXSETU_GSP_CLIENT_SECRET=... TAXSETU_GSP_PUBLIC_KEY=<pem or path> \
       python scripts/gsp_sandbox_check.py <SANDBOX_GSTIN> <portal_username> <period MMYYYY>
Route/header differences are fixed with TAXSETU_GSP_AUTH_PATH / TAXSETU_GSP_RETURN_PATH (the header names live in GspConfig.header_names)."""
import sys

from taxsetu_api import gsp_live

if len(sys.argv) != 4:
    sys.exit(__doc__)
gstin, user, period = sys.argv[1:]
cfg = gsp_live.GspConfig.from_env()
if cfg is None:
    sys.exit("set TAXSETU_GSP_BASE_URL, TAXSETU_GSP_CLIENT_ID, TAXSETU_GSP_CLIENT_SECRET and TAXSETU_GSP_PUBLIC_KEY first")
if "sandbox" not in cfg.base_url.lower() and input(f"{cfg.base_url} does not look like a sandbox. Type YES to continue: ") != "YES":
    sys.exit("stopped")


def step(name, fn):
    try:
        r = fn()
        print(f"OK    {name}")
        return r
    except gsp_live.GspError as e:
        print(f"FAIL  {name}: {e}\n      -> compare with docs/GSP.md 'Sandbox run': check the route/header names your GSP documents, then re-run")
        sys.exit(1)


s = gsp_live.GspSession(cfg, gstin, user)
step("request OTP (GSTN texts the taxpayer's mobile)", s.request_otp)
step("verify OTP and open a session", lambda: s.verify_otp(input("OTP from the sandbox taxpayer: ").strip()))
reply = step("RETSAVE a GSTR-3B draft", lambda: s.call("RETSAVE", "GSTR3B", period, {"gstin": gstin, "fp": period, "sup_details": {}}))
print("reply keys:", sorted(reply))
print("OK    the client needs reference_id/ref_id in the reply" if (reply.get("reference_id") or reply.get("ref_id")) else
      "DIFF  no reference_id/ref_id in the reply: map your GSP's field in LivePortalProvider.file (gsp_live.py)")
print("Nothing was filed. Paste the 'reply keys' line and any FAIL/DIFF lines into the project so the client can be adjusted.")
