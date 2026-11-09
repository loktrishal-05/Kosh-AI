# TaxSetu × Tally: "Tally without knowing Tally"

Goal: a small business owner (or their part-time accountant) who has never learned Tally can keep their books correct by
talking to TaxSetu in plain language, forwarding bills and uploading a bank statement. TaxSetu drafts the Tally entries, a human
approves them, and a small program on the Tally PC posts them. The business pays for far less Tally maintenance work.

## 1. What we learned about Tally (research)

| Fact | Source | Consequence for us |
|------|--------|--------------------|
| TallyPrime runs an HTTP server (default port 9000, enabled in *F1 Help → Settings → Advanced Configuration*). External apps POST an XML `ENVELOPE` with `TALLYREQUEST` = Import / Export / Execute. At least one company must be open. | [Tally XML integration](https://help.tallysolutions.com/xml-integration/) | The XML path works on every TallyPrime and Tally.ERP 9 install. It is our primary integration. |
| Import payload = `IMPORTDATA` → `REQUESTDESC` (`REPORTNAME` Vouchers / All Masters, `STATICVARIABLES/SVCURRENTCOMPANY`) → `REQUESTDATA` → `TALLYMESSAGE` → `VOUCHER` (`VCHTYPE`, `ACTION`) or `LEDGER`. | same | Always pin `SVCURRENTCOMPANY`, otherwise data lands in whatever company is active. |
| Export = `TYPE` Data / Collection / Object with `ID` naming the report; replies carry `STATUS` 1 or 0. | same | We can read ledgers and the Day Book back, to learn the books and to reconcile. |
| Native JSON (`JSONEx`) exists from TallyPrime 7.0. | [Tally JSON integration](https://help.tallysolutions.com/tally-prime-integration-using-json-1/) | Later option. XML stays the baseline because most customers are not on 7.0. |
| TallyPrime can also act as an ODBC server and exposes collections to Excel/VB. | [Tally ODBC](https://help.tallysolutions.com/odbc-integrations/) | Not needed. XML export covers the same reads. |
| GST rates and HSN/SAC can live at company, group, ledger, stock-item or voucher level; the most specific wins. Party masters need GSTIN, registration type, place of supply. | [Setting up GST in TallyPrime](https://help.tallysolutions.com/setting-up-gst-in-tallyprime/) | A wrong or half-done setup is the root of most later pain. Our setup wizard creates a consistent ledger set once. |
| Typical user pain: wrong or blank GSTIN/HSN makes vouchers "uncertain" and drops them from GSTR-1; manual bank reconciliation takes hours; recurring entries are re-keyed monthly. | [Tally data-entry challenges](https://hisabkitab.co/common-challenges-in-tally-data-entry-and-how-automation-solves-them), [GST ledger mistakes](https://suvit.io/post/mistakes-to-avoid-in-tally-gst-ledgers) | These are the first things we automate and check. |
| The Tally port has no password. | third-party guide | Never expose it to the internet. Only a local bridge talks to it. |

Not verified: every voucher shape below is built from Tally's documented structure but has **not** been run against a live
TallyPrime. The bridge has a `selftest` and a dry-run mode so the first real install proves it before any data is posted.

## 2. Architecture

```mermaid
flowchart LR
  subgraph Owner["Business owner (no Tally knowledge)"]
    W["WhatsApp / web: type, speak, photo, bank CSV"]
  end
  subgraph Cloud["TaxSetu cloud (Vercel + Neon)"]
    C["Classifier<br/>(rules first, LLM assist)"]
    B["Books engine<br/>voucher + ledger XML, GST split, balance check"]
    Q["Approval queue<br/>(outbox, hash + HMAC)"]
    A[("Audit chain")]
  end
  subgraph PC["Customer PC"]
    BR["tally-bridge<br/>(stdlib Python)"]
    T["TallyPrime<br/>HTTP :9000"]
  end
  W --> C --> B --> Q
  Q -->|"human approves exact hash"| A
  BR -->|"poll, verify hash + signature"| Q
  BR -->|"XML import"| T
  T -->|"response / ledger + day-book export"| BR -->|"ack + sync"| Q
```

Design rules (same spirit as the filing gate):

1. **AI drafts, deterministic code decides.** The LLM may extract fields from text; amounts, GST split, balance and ledger
   names are validated by Python. Anything the classifier is unsure about becomes a plain-language *question*, never a guess.
2. **Nothing reaches Tally without human approval of the exact bytes.** The approver confirms the payload SHA-256; the cloud
   signs it with a per-bridge key; the bridge re-verifies before posting.
3. **The bridge can only import vouchers and masters.** It refuses `Delete`, `Cancel`, `Execute` and any other request type.
4. **The cloud never reaches into the PC.** The bridge dials out (poll), so no inbound port is opened and Tally's open port
   stays on localhost.
5. **Learning, not hardcoding.** A per-tenant alias table remembers "Sharma → Rent Paid" after one confirmation.

## 3. Work packages

| # | Package | Where | Status |
|---|---------|-------|--------|
| 1 | Shared models (`VoucherDraft`, `Line`, `LedgerSpec`, `BankTxn`, `BookContext`) | `engine/tally_models.py` | contract |
| 2 | Books engine: voucher/ledger XML, GST-aware drafts, response + export parsers, starter chart of accounts | `engine/tallybooks.py`, `engine/tally_coa.py` | Codex A |
| 3 | Classifier (text → voucher) and bank-statement CSV parser + categoriser | `engine/tally_classify.py`, `engine/tally_bank.py` | Codex B |
| 4 | Bridge agent for the customer PC | `apps/tally-bridge/` | Codex C |
| 5 | Outbox + alias store, migration 0003 (RLS), API routes (sandbox + authenticated + bridge), MCP tools | `apps/api-gateway`, `infra/migrations`, `mcp-servers` | me |
| 6 | "Tally Assistant" UI: setup wizard, type-an-entry, bank-statement review, bridge pairing, plain-language glossary | `apps/ca-workbench-web` | after 5 |
| 7 | Deploy workbench, wire to API, README + screenshots | Vercel | after 6 |

Out of scope for now: Tally JSON (7.0+), TDL customisation, stock/inventory vouchers (accounting vouchers only), multi-company
switching, e-invoice/e-way bill generation from Tally, live GSP filing.
