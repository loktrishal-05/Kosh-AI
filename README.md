<div align="center">

# Kosh AI

**An agentic compliance co-pilot for Indian micro-enterprises.**
WhatsApp-first for the owner · multi-client workbench for the CA · a human OTP is the only thing that can file.

[![tests](https://github.com/loktrishal-05/taxsetu-ai/actions/workflows/test.yml/badge.svg)](https://github.com/loktrishal-05/taxsetu-ai/actions/workflows/test.yml)
![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![tests](https://img.shields.io/badge/tests-967%20passing-2ea44f)
![money](https://img.shields.io/badge/money-Decimal%20only-0b6b57)
![filing](https://img.shields.io/badge/filing-human%20OTP%20only-b60205)

</div>

> *Naming: the product is **Kosh AI**. The GitHub repository, the Vercel projects and the Python packages (`taxsetu_*`) keep their original `taxsetu` names so nothing breaks; only visible text was renamed.*
>
> **Problem statement 3.1.** A shop owner with a phone and a shoebox of bills should not need to understand GSTR-2B, Rule 37,
> Section 194C or Circular 64/38 to stay compliant. Kosh AI reads the bills, does the arithmetic, chases the suppliers, drafts the
> replies, and then **stops** — filing stays with the owner or a professional.

![Sandbox storyline](docs/assets/storyline-1-ingestion.jpg)

---

## Contents

1. [Design principles](#design-principles)
2. [Architecture](#architecture)
3. [The five agents](#the-five-agents)
4. [Workflows](#workflows)
5. [MCP server mesh](#mcp-server-mesh)
6. [Data model and tenant isolation](#data-model-and-tenant-isolation)
7. [What the deterministic engine covers](#what-the-deterministic-engine-covers)
8. [Security model](#security-model)
9. [Screenshots](#screenshots)
10. [API reference](#api-reference)
11. [Repository layout](#repository-layout)
12. [Quickstart](#quickstart)
13. [Testing](#testing)
14. [Deployment](#deployment)
15. [Tally Assistant](#tally-assistant)
16. [Books from your notebook](#books-from-your-notebook)
17. [Hackathon fit: Tech4Bharat problem 3.1](#hackathon-fit-tech4bharat-problem-31)
18. [Status, limits and roadmap](#status-limits-and-roadmap)

---

## Design principles

| # | Principle | How it is enforced in code |
|---|-----------|----------------------------|
| 1 | **Neuro-symbolic split.** LLMs only *extract, classify and draft*. They never compute tax, interest, TDS or ITR. | All arithmetic lives in `packages/deterministic-tax-engine`, which has no LLM import. Agents call it; LLM output is validated before use. |
| 2 | **Agents prepare, humans file (FR-025).** | Agents receive an `AgentTools` object with only `stage` and `get`. The MCP mesh refuses to register any tool named like `retfile`, `file_*`, `ims_reject`, `authorize`, `otp`. |
| 3 | **Non-repudiation.** A filing is bound to the exact bytes the owner saw. | Single-use OTP bound to `SHA-256(payload)`; any edit invalidates it; the portal re-verifies an HMAC approval token; audit events are hash-chained. |
| 4 | **Exact money.** | `Decimal` end-to-end, HALF_UP rounding, and the API serialises money as strings (never floats). |
| 5 | **No hallucinated law.** | A citation is usable only if it resolves in the effective-dated statutory corpus; Circular 64/38 relief is unlocked by a deterministic gate first. |
| 6 | **Tenant isolation in the database, not the app.** | PostgreSQL `FORCE ROW LEVEL SECURITY` keyed on `app.tenant_id`, with a non-bypass application role. |
| 7 | **Bounded autonomy.** | Every agent graph has a hard step cap; supplier nudges are capped at 3 per invoice with a 48 h cooldown, enforced in the tool *and* the engine. |

---

## Architecture

```mermaid
flowchart LR
  subgraph Channels
    WA["WhatsApp<br/>(owner, clerk, driver)"]
    CA["CA workbench<br/>(Next.js, mock data)"]
  end

  subgraph Edge["API gateway (FastAPI)"]
    WH["Signed, idempotent<br/>webhook"]
    JWT["JWT roles<br/>OWNER CLERK CA DRIVER EMPLOYEE"]
    GATE["HITL gate<br/>stage / OTP / authorize"]
    AUD[("Hash-chained<br/>audit log")]
  end

  subgraph Brain["Agent layer (state machines, hard step cap)"]
    A1["1 Ingestion"]
    A2["2 Recon + chase"]
    A3["3 Logistics + MOV-07"]
    A4["4 Direct tax"]
    A5["5 Explainer + hand-off"]
    LLM["LLM seam<br/>extract / draft only"]
  end

  subgraph Mesh["MCP mesh (JSON-RPC 2.0)"]
    M1["gstn-nic"]
    M2["tally-xml"]
    M3["whatsapp-voice"]
    M4["paytm-upi-aa"]
    M5["incometax-traces"]
    M6["statutory-rag"]
    M7["mca-labour"]
    M8["gworkspace-sync"]
  end

  ENG["Deterministic tax engine<br/>Decimal only, zero LLM"]
  PG[("PostgreSQL 16<br/>RLS + pgvector")]
  PORTAL["Portal provider<br/>Mock; GST via GSP when configured; ERI later"]

  WA --> WH --> A1 & A3
  CA --> JWT --> GATE
  A1 & A2 & A3 & A4 & A5 --> LLM
  A1 & A2 & A3 & A4 & A5 --> ENG
  A1 & A2 & A3 & A4 & A5 --> Mesh
  M1 & M5 -. "stage only" .-> GATE
  GATE --> AUD
  GATE -- "HMAC approval token" --> PORTAL
  GATE --> PG
```

**Reading the diagram.** Agents sit in the middle and can reach exactly two things: the deterministic engine (pure functions) and the
MCP mesh (a fixed list of tools). There is no arrow from the agent layer to the portal. The only path to the portal runs through the
gate, and the gate only moves when a human supplies a valid OTP.

### Layers at a glance

| Layer | Package | Responsibility |
|-------|---------|----------------|
| Engine | `packages/deterministic-tax-engine` | GST, TDS, ITR routing, presumptive tax, refunds, 2B reconciliation, e-Way Bill, MOV-07 gate, split-pay, Tally XML, Rule 138E watchdog, TDS interest, 30-day planner, Labour Form A/B |
| MCP mesh | `packages/mcp-servers` | Eight tool/resource servers with a JSON-RPC 2.0 core and an air-gap name guard |
| Agents | `packages/agents` | Five graph-shaped agents, an `Llm` protocol with a deterministic stub and a Claude adapter, a loop-capped graph runner |
| Gateway | `apps/api-gateway` | FastAPI edge, JWT roles, WhatsApp webhook, HITL gate, mock portal, audit chain, optional Postgres store, sandbox storyline |
| Workbench | `apps/ca-workbench-web` | Next.js 15 CA console: 80-client exception matrix, GSTR-2B diff viewer, Tally XML export (mock data, cannot file) |
| Infra | `infra/` | Postgres schema with row-level security, docker-compose (Postgres, Redis, MinIO) |

---

## The five agents

| Agent | Trigger | What it does | What it *cannot* do |
|-------|---------|--------------|---------------------|
| **1 Ingestion** | Bill photo / PDF on WhatsApp | Extract → validate GSTIN checksum → de-duplicate (`SHA-256(gstin + normalised inv no + FY)`) → supplier trust score from GSTN history → GST split, §17(5) blocked-credit check, TDS → send a one-tap approval card | Guess on a bad extraction (returns `NEEDS_REVIEW`); move money |
| **2 Recon + chase** | 14th of the month (GSTR-2B ready) | 4-way match (exact / fuzzy ≤2 edits / mismatch / missing), Rule 37 180-day clock, one nudge attempt per invoice per run | Send a 4th nudge, or nudge inside 48 h — it escalates to the CA queue |
| **3 Logistics** | Plate + invoice photo, or a detention notice | Validate OCR'd plate, check Rule 138E blocking, block duplicate EWBs, stage an EWB with a 4-hour pre-expiry alert, draft the MOV-07 reply | Cite Circular 64/38 without a valid invoice + clerical defect + a citation that resolves in the corpus |
| **4 Direct tax** | Month-end / year-end | Presumptive income from GST sales vs bank credits, 5 % cash-ceiling guardrail, ITR form routing, stage the ITR, diagnose unclaimed refunds and draft §119(2)(b) petitions | Stage a presumptive ITR once the cash ceiling is breached (escalates to CA); use ITR-U for a refund |
| **5 Explainer + hand-off** | Before each deadline | Build Tally XML packets for the CA, stage the return, produce a vernacular voice summary | Say a number the engine did not produce — ungrounded prose is replaced by a fixed template |

---

## Workflows

### 1. Human-in-the-loop filing (the non-repudiation gate)

```mermaid
sequenceDiagram
  autonumber
  participant Ag as Agent
  participant G as HITL gate
  participant O as Owner / CA
  participant P as Portal (mock)
  participant L as Audit log

  Ag->>G: stage(tenant, kind, payload)
  G->>L: RETSAVE {draft_id, sha256}
  G-->>Ag: draft_id, payload_sha256, DRAFT_STAGED
  Note over Ag,G: Agents have no other method. File / approve / reject do not exist for them.
  O->>G: request_otp(draft_id)
  G->>L: OTP_ISSUED
  G-->>O: 6-digit OTP (EVC / Aadhaar in production)
  O->>G: authorize(draft_id, payload_sha256, otp)
  alt hash differs, OTP wrong, expired or reused
    G->>L: FILING_REJECTED
    G-->>O: refused (OTP is burned either way)
  else all match
    G->>P: file(payload, HMAC(draft_id, sha256))
    P-->>G: ack_no (ARN / ITR-V, simulated)
    G->>L: RETFILE_HITL {ack_no, method}
    G-->>O: FILED_VERIFIED
  end
```

Edit a draft after the OTP is issued and its hash changes, so the OTP no longer matches. Missing and foreign drafts return the same
`draft not found`, so a tenant cannot probe for other tenants' draft ids.

### 2. Supplier bill to split payment

```mermaid
flowchart TD
  B["Bill photo on WhatsApp"] --> X["LLM extracts fields"]
  X --> V{"GSTIN checksum,<br/>date, amounts valid?"}
  V -- no --> R["NEEDS_REVIEW<br/>(no card sent)"]
  V -- yes --> D{"Seen before?"}
  D -- yes --> DUP["DUPLICATE"]
  D -- no --> T["Supplier trust score 0-900<br/>from filing history"]
  T --> S["Engine: GST split, s17(5), TDS"]
  S --> Q{"Trust score >= 800?"}
  Q -- yes --> F["Pay base + GST upfront"]
  Q -- no --> E["Pay base now, TDS withheld,<br/>GST held in escrow"]
  F & E --> C["One-tap approval card to owner"]
  C --> U["Owner's UPI PIN moves money"]
  E --> Z{"Invoice appears in GSTR-2B?"}
  Z -- yes --> REL["Release escrow to supplier"]
  Z -- no --> REF["Refund escrow to buyer"]
```

Worked example from the report: an invoice of ₹1,00,000 + 18 % GST, supplier below the trust threshold, 194C at 2 % →
**₹98,000 pay now · ₹2,000 TDS · ₹18,000 GST escrow** (conserved: the split asserts `base + TDS + escrow = total`).

### 3. Checkpoint defence (MOV-07)

```mermaid
flowchart TD
  N["Detention notice photographed"] --> K{"Valid tax invoice<br/>on file?"}
  K -- no --> X1["Exposure = 200% of tax (s129)<br/>escalate to CA, nothing cited"]
  K -- yes --> D{"Defect type"}
  D -- "plate typo <= 2 chars,<br/>PIN error, HSN same rate" --> OK["Rs 1,000 penalty (s125)"]
  D -- "plate differs by more,<br/>expired validity, other" --> X1
  OK --> RAG{"CBIC-64/38/2018-GST resolves<br/>in the statutory corpus?"}
  RAG -- yes --> LET["Draft reply, owner taps Send"]
  RAG -- no --> X1
```

In the sandbox this is the headline number: **₹72,000 exposure drops to ₹1,000** for a one-character plate typo, and stays at
₹72,000 with *no* citation when the invoice is missing.

### 4. Monthly compliance rhythm

| Day | Who | What happens |
|----:|-----|--------------|
| daily | Owner / clerk / driver | Bills, plates and notices go to WhatsApp; Agents 1 and 3 respond within seconds |
| 9-10 | Agent 5 | Tally packets and the vernacular summary are prepared for the CA and the owner |
| 11 | Deadline | GSTR-1 |
| 14 | Agent 2 | GSTR-2B is ready: reconcile, then nudge 1 to each defaulting supplier |
| 16, 18 | Agent 2 | Nudges 2 and 3, never closer than 48 h; the fourth attempt escalates to the CA exception queue |
| 18-19 | Owner / CA | Review staged drafts; owner approves with the OTP |
| 20 | Deadline | GSTR-3B |
| 31 Jul | Deadline | ITR (presumptive filers) |

---

## MCP mesh

Eight isolated servers speak MCP's JSON-RPC 2.0 (`initialize`, `tools/list`, `tools/call`, `resources/templates/list`,
`resources/read`) over stdio: `python -m taxsetu_mcp <server>`. Agents use the in-process `Client` with the same call surface.

| Server | Tools (hitl-annotated in *italics*) | Resources | State |
|--------|-------------------------------------|-----------|-------|
| `gstn-nic` | `stage_gstr1_or_3b_retsave`, *`generate_eway_bill_v103`*, *`extend_or_update_ewb_part_b`*, *`draft_mov07_circular_64_38_reply`* | `gst://taxpayer/{gstin}/public-profile`, `gst://returns/{gstin}/{period}/gstr2b` | Mock sandbox |
| `tally-xml` | *`post_tally_voucher`*, *`create_party_ledger`* | `tally://company/active/masters`, `…/daybook/{date}` | Dry-run transport; XML validated and balance-checked |
| `whatsapp-voice` | `send_interactive_approval_card`, `dispatch_supplier_2b_nudge`, `push_vernacular_voice_summary` | `whatsapp://thread/{phone}/history` | Mock outbox; nudge cap enforced here |
| `paytm-upi-aa` | *`execute_split_vendor_payout`* (creates an *intent* only), `release_or_refund_gst_escrow`, `generate_smart_compliance_receipt` | `bank://aa/{pan}/statements/{month}`, `escrow://gst-holds/active` | Mock; partial receipt |
| `incometax-traces` | `evaluate_itr_eligibility_1_to_7`, `compute_presumptive_44ad_44ada_44ae`, *`validate_and_stage_itr_json`*, *`generate_sec_119_2b_condonation_petition`* | `itd://pan/{pan}/ais-tis/{ay}`, `…/form26as/{ay}`, `…/5yr-unclaimed-refunds` | Mock sandbox |
| `statutory-rag` | `search_effective_dated_statute`, `verify_citation`, `verify_hsn_sac_tax_rate` | `law://cgst/section/{n}`, `law://incometax/section/{n}`, `law://cbic/circulars/{no}` | Keyword ranking over a small corpus |
| `mca-labour` | `compile_labour_registers_form_a_and_b`, `draft_spice_plus_emoa_inc33`, `draft_eaoa_inc34_with_entrenchment`, `parse_form16_certificate` | — | All draft-only (`hitlRequired`); outputs carry `status: DRAFT` and a CA/CS-review disclaimer. Samples in `docs/samples/` are synthetic |
| `gworkspace-sync` | `sync_compliance_schedule_to_calendar`, `archive_signed_returns_to_drive` | `gdrive://audit-vault/{fy}/{month}` | In-memory; archives only filed (acknowledged) documents |

---

## Data model and tenant isolation

```mermaid
erDiagram
  tenants ||--o{ gst_registrations : has
  tenants ||--o{ invoices_inward_outward : owns
  tenants ||--o{ eway_bills_and_detentions : owns
  tenants ||--o{ direct_tax_and_employee_records : owns
  tenants ||--o{ corporate_and_labour_registers : owns
  tenants ||--o{ hitl_approvals_and_audit_log : "append-only"
  invoices_inward_outward {
    uuid tenant_id FK
    text dedup_hash "UNIQUE per tenant"
    numeric taxable_value
  }
  hitl_approvals_and_audit_log {
    uuid tenant_id FK
    text prev_event_hash
    text event_hash
  }
```

* Seven tables, every one with `ENABLE` **and** `FORCE ROW LEVEL SECURITY`, policy `tenant_id = current_setting('app.tenant_id', true)`.
* The application connects as `taxsetu_app` (`NOSUPERUSER NOBYPASSRLS`); with no tenant set, queries return zero rows.
* The audit table is granted `SELECT, INSERT` only — it is append-only by privilege as well as by policy.
* Static checks and the live cross-tenant tests run on every CI build against a Postgres service container.

### Persistence (optional, enabled by `DATABASE_URL_APP`)

| Concern | Design |
|---------|--------|
| Drafts | `hitl_drafts` table under RLS; each call runs in its own transaction with `app.tenant_id` set, so isolation is the database's job |
| Audit chain | One hash chain **per tenant** (a tenant can only see its own rows). The canonical JSON each hash covered is stored, so verification re-hashes exactly what was signed. Appends take a per-tenant advisory lock so concurrent writers cannot fork the chain |
| OTP double-spend | Optimistic `version` check; the OTP is burned and saved *before* filing, so a concurrent loser fails instead of filing twice |
| Tamper evidence | The app role has `SELECT, INSERT` only on the audit table; a rewrite by the table owner is caught by `verify()` |
| Fallback | Without a database URL the same gate runs in memory (tests, sandbox) |
| Hosted (Vercel + Neon) | `DATABASE_URL` is the owner URL injected by the Neon integration; the API **re-points it at the RLS-bound `taxsetu_app` role** using `TAXSETU_APP_PASSWORD`, so it never runs as the owner. It refuses to boot on Postgres with the default `HITL_SIGNING_SECRET`, and `/health` reports the connected role and `bypass_rls` |

---

## What the deterministic engine covers

| Area | Coverage |
|------|----------|
| **GST** | GSTIN Mod-36 checksum, PAN format; CGST/SGST/IGST split (SGST absorbs the rounding paisa); §17(5) blocked credit (prefix/keyword heuristic); GTA 5 % RCM; Rule 37 180-day clock; §47 late fee; §50 interest |
| **TDS** | 194C (single/aggregate threshold catch-up, 1 %/2 %), 194J (10 %/2 % technical), 194H, 194Q; GST excluded from the base; no PAN → 20 % |
| **Income tax** | New/old slabs AY 2026-27, 87A rebate + marginal relief, 4 % cess, regime comparison; 44AD / 44ADA / 44AE; 5 % cash-ceiling guardrail (WARN ≥ 3.8 %, BREACH > 5 %); ITR-1…7 router |
| **Refunds** | Six pathways (139(1), 139(4), 139(5), §119(2)(b) condonation to 31 Mar of AY+6, Form 30, §154) plus reissue; ITR-U is never offered for a refund |
| **Reconciliation** | 4-way GSTR-2B match with Levenshtein ≤ 2; nudge governor (max 3, 48 h cooldown) |
| **e-Way Bill** | Validity (1 day / 200 km, expiry at midnight), ±8 h extension window, 4 h pre-expiry alert, MOV-07 / Circular 64-38 eligibility |
| **Payments** | Supplier GST trust score 0–900, three-way split, balanced multi-ledger postings, MDR/TCS/TDS unbundling, Tally purchase-voucher XML |

> Rates and thresholds are encoded from the source report plus AY 2026-27 slabs and live in single tables so a CA can audit and edit
> them. **Treat every figure as unverified until a practising CA signs it off.**

---

## Security model

| Threat | Mitigation | Test |
|--------|-----------|------|
| Prompt-injected agent tries to file or reject | No such tool exists; names are blocked at registration; gate needs a human OTP | `test_hitl_airgap`, `test_forbidden_tool_names_cannot_even_be_registered` |
| OTP replay / brute force | Single-use (burned on success *and* failure), 300 s TTL, bound to payload hash | adversarial suite |
| Edit-after-approval swap | Edit re-hashes the draft and voids the OTP; portal re-checks HMAC over the hash | adversarial suite |
| Cross-tenant read / write | RLS + same error for missing vs foreign drafts | `test_rls_isolation`, adversarial suite |
| Audit tampering | SHA-256 hash chain, `verify()`; append-only grants | adversarial suite |
| Duplicate bill / duplicate EWB | Composite dedup hash checked before posting or generating | agents tests |
| Supplier-chasing loop | Cap in the WhatsApp tool + engine + graph step cap | `test_recon_agent_loop_is_capped…` |
| Hallucinated statute | Citations must resolve in the effective-dated corpus | MCP + agents tests |
| Hallucinated figures in owner summaries | Every number in LLM prose must equal an engine output, else fixed template | `test_explainer_rejects_llm_prose…` |
| Float drift in money | `Decimal` everywhere; API emits strings | e2e tests |
| WhatsApp webhook forgery / replay | HMAC signature check; idempotent on `wamid` | e2e tests |

---

## Screenshots

These are real captures of the running application (`GET /` → "Run the end-to-end storyline"). One click executes all five agents,
the MCP mesh and the approval gate on fake data and renders the result.

| | |
|---|---|
| **Agent 1–2 · bill to split payment, 2B reconciliation** | ![Agent 1 ingestion](docs/assets/storyline-1-ingestion.jpg) |
| **Agent 3–5 · MOV-07 defence (₹72,000 → ₹1,000), ITR-4, Hindi voice summary** | ![Agents 3-5](docs/assets/storyline-2-defence-itr-handoff.jpg) |
| **Human gate · wrong OTP refused, correct OTP files, audit chain intact** | ![Human gate](docs/assets/storyline-3-human-gate.jpg) |
| **OpenAPI explorer (`/docs`)** | ![API docs](docs/assets/api-docs.jpg) |
| **CA workbench · exception matrix: 80 clients, four batch filters, priority-sorted** | ![Exception matrix](docs/assets/workbench-matrix.jpg) |
| **CA workbench · client GSTR-2B diff: typos, tax mismatches and missing records flagged with text, not colour alone** | ![2B diff](docs/assets/workbench-2b-diff.jpg) |

---

## API reference

Paths below are relative to `/api/v1` unless they start with `/health` or `/`. All routes except `/`, `/health`, `/docs`, the sandbox storyline and the HMAC-signed WhatsApp webhook require a bearer JWT.

| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/` | — | Sandbox landing page |
| GET | `/health` | — | Liveness, store (`memory`/`postgres`), audit-chain validity |
| GET | `/api/v1/demo/storyline` | — | Runs the whole flow on fake data, statelessly |
| POST | `/webhooks/whatsapp` | HMAC | Signed, idempotent inbound messages |
| POST | `/gst/{gstin}/reconcile-2b` | OWNER, CA | Deterministic 4-way reconciliation |
| POST | `/ewb/generate-or-defend` | OWNER, CLERK, DRIVER | Stage an EWB or classify a MOV-07 defect |
| POST | `/itr/{pan}/compute-and-stage` | OWNER, CA, EMPLOYEE | Presumptive income, routing, stage ITR |
| GET | `/refund-pathway` | OWNER, CA, EMPLOYEE | Which of the six refund pathways applies |
| POST | `/hitl/request-otp/{draft_id}` | OWNER, EMPLOYEE, CA | Issue the single-use OTP |
| POST | `/hitl/authorize-filing` | OWNER, EMPLOYEE | Verify OTP + hash, file to the mock portal |
| GET | `/gsp/status` | OWNER, CA, EMPLOYEE | Is live GST portal access configured on this server |
| POST | `/gsp/otp` | OWNER, CA | Ask the GST portal to text the taxpayer's mobile an OTP (live mode only) |
| POST | `/gsp/session` | OWNER, CA | Open the portal session with that OTP; sessions persist in Postgres |
| GET | `/audit` | OWNER, CA | Tenant-scoped, hash-chained events |

**Approval OTP delivery.** With no live portal and no delivery channel configured (the demo), `/hitl/request-otp` echoes `mock_otp`. In live mode it never does: set `TAXSETU_OTP_WEBHOOK_URL` (https, optional `TAXSETU_OTP_WEBHOOK_TOKEN`) and the server posts the tenant, draft and OTP to your SMS/WhatsApp gateway; with no webhook it answers 503.

---

## Repository layout

```text
taxsetu-ai/
├── packages/
│   ├── deterministic-tax-engine/   Decimal-only statutory logic        (no LLM)
│   ├── mcp-servers/                8 MCP servers + JSON-RPC core
│   ├── agents/                     5 agents, graph runner, Llm protocol + stub
│   ├── statutory-rag/              (reserved: pgvector + BM25 corpus)
│   ├── schemas-cbdt-gstn/          (reserved: official JSON-schema validators)
│   └── tally-xml-bridge/           (reserved: TallyPrime bridge)
├── apps/
│   ├── api-gateway/                FastAPI edge, HITL gate, mock portal, audit, sandbox
│   ├── ca-workbench-web/           Next.js 15 CA console (mock client matrix), owner view, impact model, Tally and Books pages
│   ├── tally-bridge/               Program for the customer PC: posts approved XML into TallyPrime (stdlib only)
│   └── mock-gov-portals/           (planned) portal UIs
├── infra/                          Postgres RLS migrations (0001 core ... 0006 books GST, 0007 GSP sessions), docker-compose
├── tests/                          unit · adversarial · e2e-demo · infra · mcp · agents
├── docs/                           PLAN.md, screenshots
├── index.py                        Vercel entrypoint
├── Dockerfile · render.yaml        Long-running deployment
└── .github/workflows/test.yml      CI
```

---

## Quickstart

```bash
git clone https://github.com/loktrishal-05/taxsetu-ai && cd taxsetu-ai
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pytest httpx uvicorn fastapi "pydantic>=2" \
  -e packages/deterministic-tax-engine -e packages/mcp-servers -e packages/agents -e apps/api-gateway

pytest tests -q                                           # 723 pass, 5 live-Tally tests skipped (Postgres tests skip if no database is reachable)
uvicorn --factory taxsetu_api.main:create_app --port 8000 # then open http://localhost:8000
```

Optional local infrastructure and the live row-level-security test:

```bash
docker compose -f infra/docker-compose.yml up -d postgres # Postgres 16 + pgvector (migrations apply on first boot)
pip install "psycopg[binary]" && pytest tests/infra -q    # live RLS + persistence tests
DATABASE_URL_APP=postgresql://taxsetu_app:taxsetu_app@localhost:5432/taxsetu \
  uvicorn --factory taxsetu_api.main:create_app --port 8000   # drafts + audit now durable
```

CA workbench (Node 24+):

```bash
cd apps/ca-workbench-web && npm install && npm test && npm run build && npm run start   # http://localhost:3000
```

Configuration lives in environment variables (see `.env.example`): `DATABASE_URL`, `REDIS_URL`, `PORTAL_MODE=mock`,
`WHATSAPP_APP_SECRET`, `LLM_API_KEY`, and **`HITL_SIGNING_SECRET` — set a long random value in any shared environment**; the built-in
default exists only for local development.

---

### Signing in (evaluation build)
**Open https://taxsetu-workbench.vercel.app** (public: no Vercel account is needed; Vercel's own login only guards the long preview-style addresses). The workbench opens on a **sign-in page**. Click **Demo admin**: the username and password fill in on screen and the sign-in carries on by itself, landing on the workbench as "Demo Admin · OWNER (demo)"
(you can also type `demo.admin` / `Demo@2026`). One session is shared by the Clients, Books and Tally Assistant pages, and **Sign out** clears it.

![Demo admin: the details fill in, then it signs in](docs/assets/signin-demo-filled.png)

How it is built so real authentication can replace it later without touching the pages: the demo account is **off unless the API server has `TAXSETU_DEMO_LOGIN=1`** (the button only appears when the server says it is on);
it can only reach the one shared demo workspace; wrong passwords are throttled; the session is the same signed token and the same OWNER/CA/CLERK role checks the rest of the API already enforces.
For production: leave `TAXSETU_DEMO_LOGIN` unset and replace `authenticate()` in `apps/api-gateway/taxsetu_api/login.py` with a user store (hashed passwords) or an identity provider (OIDC or mobile OTP);
the sign-in page, token format and role checks stay as they are. The browser-side gate only decides what to show; the API enforces tenants and roles on every call.

## Testing

| Suite | Tests | What it proves |
|-------|------:|----------------|
| `tests/unit` | 717 | Every statutory rule, boundary and rounding case: GST, TDS, ITR, refunds, payments, Tally XML, planner (138E, 201(1A), schedule), labour registers (Verhoeff, masking, wage math), Form 16 parse/reconcile, e-MOA/e-AOA drafting, Neon URL re-pointing |
| `tests/adversarial` | 13 | Air-gap, OTP replay / expiry / burn, edit-after-OTP, cross-tenant, audit tamper, prompt injection |
| `tests/e2e-demo` | 68 | The report's demo storyline over HTTP, including the sandbox endpoint |
| `tests/mcp` | 26 | JSON-RPC shapes, forbidden tool names, each server's business rules, nudge cap, labour registers |
| `tests/agents` | 49 | Each agent end to end, loop caps, dedup, Rule 138E stop, grounded-number guard, Claude adapter (fake client) |
| `tests/infra` | 31 | RLS on every table, append-only audit, **live Postgres**: restart survival, tenant isolation, OTP double-spend, audit tamper, concurrent appends, API on Postgres |
| `tests/bridge` | 36 | Tally bridge against fake Tally and cloud servers: tampered XML, bad signature, wrong company, Delete refused, DOCTYPE refused, double-post guard, dry-run |
| `apps/ca-workbench-web` | 43 | Money formatting, XML escaping, balanced vouchers, priority ordering, Tally flow helpers (`node:test`) |
| **Total** | **924 Python passing + 43 workbench** (26 skipped locally: Postgres and live-Tally tests need those running; CI runs the Postgres ones) | **all passing** |

CI runs the Python suite on every push (Python 3.10) with a Postgres service container, so the database tests run there too.

---

## Deployment

Two shapes, same code:

| Target | Config | Behaviour |
|--------|--------|-----------|
| **Vercel** (serverless) + **Neon** Postgres | `index.py`, `requirements.txt` | Production at `taxsetu-ai.vercel.app` (push to `main` auto-deploys). With the Neon database attached the HITL gate and audit chain are durable across cold instances; without it the gate is in-memory and only the stateless sandbox is meaningful. Schema from `infra/migrations/` is applied to Neon; the app role is created with a generated password stored as a sensitive Vercel variable. |
| **Render / any Docker host** (long-running) | `Dockerfile`, `render.yaml` | One process keeps the in-memory gate between requests. `HITL_SIGNING_SECRET` is generated by the blueprint. |

```bash
docker build -t taxsetu-api . && docker run -p 8000:8000 -e HITL_SIGNING_SECRET="$(openssl rand -base64 48)" taxsetu-api
```

The deployed build runs the **mock** portal only. Nothing in this repository can file a real return.

---

## Tally Assistant

Small businesses pay accountants a lot to keep Tally correct. The Tally Assistant lets an owner who has never used Tally do the
routine work in plain language: say what happened, upload a bank statement, approve the result. Research notes, sources and the
work-package plan are in [`docs/TALLY.md`](docs/TALLY.md).

![Plain-language entry](docs/assets/tally-assistant-entry.jpg)
![Bank statement review](docs/assets/tally-assistant-bank.jpg)

```mermaid
flowchart LR
  O["Owner: types a sentence,<br/>uploads a bank CSV"] --> C["Classifier<br/>rules first, optional LLM fill-in"]
  C --> D["VoucherDraft<br/>balanced, GST-aware"]
  D --> H["Human reviews and approves<br/>the SHA-256 of the exact XML"]
  H --> Q[("Outbox + audit chain<br/>Neon, RLS")]
  B["tally-bridge on the PC"] -->|"poll over HTTPS"| Q
  B -->|"verify hash + HMAC, then POST"| T["TallyPrime :9000"]
  T -->|"reply"| B -->|"ack"| Q
```

| Piece | Where | What it does |
|-------|-------|--------------|
| Books engine | `taxsetu_engine/tallybooks.py`, `tally_coa.py` | Voucher and ledger-master XML (Tally's `Import Data` envelope), GST split, TDS line, reply and export parsers, starter chart of accounts for traders / services / manufacturers with a plain-English meaning per ledger |
| Classifier | `tally_classify.py` | "Paid 25000 rent to Sharma by cheque yesterday" becomes a balanced draft. Missing amount, party or direction becomes a plain question, never a guess. Instruction-like text is flagged and ignored |
| Bank importer | `tally_bank.py` | Messy bank CSVs (junk headers, signed or Dr/Cr columns, several date formats), de-duplicated by hash. Unknown payees go to *Suspense* and cannot be sent until a person picks a ledger. Money **in** under an expense keyword is flagged for review |
| Approval + outbox | `taxsetu_api/tally_routes.py`, migration `0003_tally.sql` | Stage a batch, approve the exact hash (changed content gives 409), one decision per batch, every step in the audit chain. Learned payee names are remembered per tenant |
| Bridge | `apps/tally-bridge/` | Runs on the customer PC, dials out only, re-verifies SHA-256 and a per-bridge HMAC, accepts only `Create`/`Alter` imports of Vouchers or Masters for the paired company, journals each post before sending so a crash cannot double-post |
| UI | `apps/ca-workbench-web/app/tally` | Demo mode (no sign-in, ends in a downloadable Tally file) and connected mode (stage, approve, watch status, pair a bridge) with a glossary for novices |

**AI assist (opt-in).** When the server owner sets `ANTHROPIC_API_KEY`, three things use Claude: reading a typed sentence the keyword rules cannot parse
("paid sharma twenty five thousand for rent"), suggesting a ledger for the bank rows a person must still check, and reading a supplier bill photo into a purchase
draft. The AI only **proposes**: every figure is re-validated by code (amounts, dates, GSTIN checksum, GST recomputed, printed total compared), a suggested ledger must
come from the business's real ledgers and the row stays "needs your check", and nothing is approved without a person. It never runs on the public sandbox routes. The page
says plainly when AI is off. **Tested with a fake model only; it has not been run against the live Claude API** (no key was available), so evaluate on real bills before relying on it.

**On-server model (no key needed, opt-in).** For the ledger-suggestion and typed-sentence parts only, a small fine-tuned classifier can run on the server's CPU instead (`TAXSETU_LOCAL_MODEL=ml/artifacts/narration_v1`; see [`ml/README.md`](ml/README.md)). It was trained on synthetic data and is right about **76% of the time on wording it never saw** (86% when it is at least 90% sure, 4% on personal spending), so it only pre-fills a ledger on rows that a person must still check. It cannot read bill photos.

API (all under `/api/v1/tally`): `sandbox/*` (anonymous, stateless), `entry`, `bank-statement`, `batches` (stage, list, get, approve, reject),
`setup`, `aliases`, `ledgers`, `bridges` (create, list, revoke), and `bridge/pair|pending|ack|ledgers` for the bridge itself.
Bridge and pairing tokens use separate machine roles that no human route accepts.

**Verified against a real TallyPrime 7.2 (Education mode, 2026-11-09).** The starter chart, party ledgers and all five voucher types
(payment, receipt, contra, GST purchase, GST sale) were imported into a live test company and read back: the GST purchase of 50,000 + 18%
is stored as 4,500 CGST + 4,500 SGST with the supplier credited 59,000. The full path (production cloud, approval, bridge, real Tally) passes
`scripts/tally_e2e.py` with `TALLY_URL` and `E2E_COMPANY` set, and `tests/live` (opt-in via `TALLY_LIVE_COMPANY`) repeats the checks.
Testing against the real program found four bugs that fakes could not: Tally **rejects a ledger without a `NAME.LIST/NAME` child**;
it **writes illegal character references (`&#4;`)** that strict XML parsers refuse; our safety check **rejected any reply containing the
word `ENTITY`** (Tally has such a tag); and the **`Day Book` report returns nothing over XML**, so reads use an inline voucher collection.
A 36-row, three-month bank statement (junk header and footer, quoted amounts) went through the importer into the live Tally in one
request (0.9 s); the Bank Account ledger moved by exactly the statement's net, and Tally's own Profit & Loss matched independent
arithmetic. A 500-voucher GST batch took 22 s. Each staged voucher carries a batch-scoped `REMOTEID`, so a retried post alters the voucher
in place instead of duplicating it (re-sending 500 vouchers created 0 and altered 500). Non-English ledger names (Hindi, Tamil, accents, the
rupee sign) are stored exactly when sent as plain UTF-8; sending UTF-16 corrupted them, so the bridge stays on UTF-8.

![Real TallyPrime Profit and Loss after the imports](docs/assets/tally-real-profit-loss.png)

Not covered by a real run: other Tally versions (older Tally.ERP 9, TallyPrime 7.0/7.1), a licensed (non-Education) company, and the
Edit Log edition. Run `python tally_bridge.py selftest` and then `--dry-run` on a test company before real books.

**What has been exercised end to end.** `scripts/tally_e2e.py` drives the deployed API (Vercel + Neon) with the real bridge program and a
fake Tally on localhost: two real tenants, stage, approve the exact hash, post, ack, audit chain, cross-tenant isolation, bridge
revocation (33 checks). The workbench's Connected mode was also driven in a browser against a local stack.

![Approval and delivery](docs/assets/tally-assistant-approval.jpg)

Also known: the bank table scrolls sideways on phones; there is no real
login yet. A temporary admin-key endpoint mints 12-hour tokens (`POST /api/v1/auth/dev-token`) and creates tenants
(`POST /api/v1/auth/tenants`, audited); both are disabled unless `TAXSETU_ADMIN_KEY` is set. Stock/inventory vouchers, JSON (TallyPrime 7+),
e-invoice and multi-company are out of scope.

---

## Books from your notebook

Many small shops, freelancers and clubs keep only a notebook or cash book: dated money in and money out, with no ledger accounts. **Single entry**
cannot show profit, what is owed, or what is owned. This module turns such a record into proper **double-entry books** and keeps them over time.
Method, formulas, classification rules and limits are in [`docs/BOOKS.md`](docs/BOOKS.md).

![Books at a glance](docs/assets/books-at-a-glance.jpg)
![Statements](docs/assets/books-statements.jpg)

| Who | What they get |
|-----|---------------|
| **Business** (shop, trader) | Trading account, Profit and Loss, Balance Sheet. Credit sales and credit purchases that never touched the cash book are **derived** with the total-debtors / total-creditors method (conversion method) |
| **Club or charity** | Receipts and Payments account, Income and Expenditure (accruals: subscriptions in arrears and in advance, outstanding expenses), Balance Sheet with a Capital Fund; corpus donations go straight to the fund |
| **Individual** | Income and expense statement, savings, net worth at cost and at market value |

**Checks built in.** Every journal balances; the adjusted trial balance balances; the balance sheet balances; and an **independent cross-check** recomputes
closing net worth straight from the cash book (without reading the journal) and requires the profit to agree to the paisa.

**Keeping books over time.** Create a book per period, add lines by form or CSV, correct a wrong line by **voiding it with a reason** (nothing is ever deleted),
close the period (a snapshot of the reports is stored and the period is frozen), roll the balances into the next period, and stage the result for Tally through the
same approval queue (opening balances become a journal voucher, REMOTEIDs make a retry safe). Every step is in the audit chain. Roles: staff may enter lines;
owners and CAs correct, close, roll over and export.

API: `/api/v1/books/sandbox/*` (anonymous: examples, CSV parsing, conversion) and `/api/v1/books` (create, list, get, `setup`, `entries`, `entries/{id}/void`,
`report`, `close`, `rollover`, `tally`). UI: the **Books** page.

**How it was verified.**

| Check | Result |
|-------|--------|
| Three hand-computed textbook cases (business, club, individual), figures derived on paper before any code | all match to the paisa |
| 60 more simulated shops (GST-registered, and with an old asset sold at a loss) whose true tax paid, tax payable and loss on sale only the simulator knows | every figure equals the truth (`tests/unit/test_single_entry_gst_assets.py`) |
| 30 simulated shops whose true profit and balances only the simulator knows (credit sales and purchases are absent from the cash book) | converted profit, sales, purchases, debtors, creditors, loans, assets and capital all equal the truth |
| 600 randomised books (200 per entity type) | every invariant holds: balanced journals, trial balance, balance sheet, cross-check |
| Production (Vercel + Neon), a simulated year: save, correct, convert, close, roll over, export | converted profit is exactly the true profit; two real tenants fully isolated (`scripts/books_e2e.py`, 17 checks) |
| **Real TallyPrime 7.2**: each of the four examples exported into an empty company, then every ledger balance compared with the converter's trial balance | **0 mismatches** across business, club, individual and a 182-line kirana store (`scripts/books_tally_verify.py`) |
| The results screens run against the real converter output saved as fixtures | UI test fails if the engine's shape changes; a Python test fails if the fixtures are stale |

Real Tally found one defect that no fake could: an ordinary voucher may not post to a ledger under Tally's `Stock-in-Hand` group, so the stock ledger is filed under `Current Assets`.

**Limits, stated plainly.** Not a statutory audit: a practising CA must review before the books are relied on or filed. Profit or loss on the sale of an asset needs the asset's
book value from you (otherwise it is asked, not guessed). GST in the books is the simple case: a rate per line (amounts include GST), one rate for credit sales and one for credit purchases,
input credit set off at year end; reverse charge, composition scheme and GST on discounts/returns are not modelled and nothing is filed. Depreciation uses the rate or amount you give.
Lines the rules cannot classify are flagged `NEEDS_REVIEW` and listed as questions; closing a period with open questions needs an explicit "I have reviewed".
Verified on TallyPrime 7.2 Education mode only; Education mode accepts only vouchers dated the 1st or 2nd, so the export check moved each date to the 1st of its month.

---

## Hackathon fit: Tech4Bharat problem 3.1

Entry for GAVS Tech4Bharat, theme MSME Finance and Compliance, problem 3.1 (*Micro enterprises lose time and profit to compliance paperwork*), Agentic AI track. The brief says filing stays with the owner or a professional and is simulated; that is how this is built.

| What the brief asks for | Where it is |
|-------------------------|-------------|
| GST, TDS and e-way bill work taken off the owner | Five agents plus the deterministic engine (see above) |
| Supplier filings that break input credit | 2B reconciliation, Rule 37 and RCM adjustments, capped supplier nudges |
| A strict line between preparing and filing | Human OTP gate bound to the payload hash; the GSP path only saves drafts |
| Works for low literacy, limited connectivity, low-cost phones | `/owner`: large type, one idea per card, English, Hindi and Kannada, read-aloud, about 107 kB first load |
| Does the owner understand the return filed in their name | Plain-language cards and the explainer agent |
| What is it worth | `/impact`: a model built only from the brief's figures (15 to 20 hours a month, 1,500 to 3,000 rupees per filing); **a model, not a measured result** |

The presentation deck is authored as HTML in `apps/ca-workbench-web/public/deck/slides.html` (screenshots, diagrams and background art alongside).

**Honest gaps for this entry:** Hindi and Kannada wording is a first draft awaiting a native speaker; owner-side bill reading needs a live model key and has only run on a fake model; the live GSP path is simulator-tested only and ERI is not built; savings figures are not from a pilot.

---

## Status, limits and roadmap

| Phase | Scope | Status |
|------:|-------|--------|
| 1 | Deterministic tax engine | ✅ done |
| 6a | API gateway, HITL gate, mock portal, audit chain | ✅ done |
| 4 | Payments logic (split, trust score, ledgers, Tally XML) | ✅ core done · UI and UPI rails pending |
| 2 | MCP mesh | ✅ done on mock backends · `mca-labour` generators pending |
| 3 | Five agents | ✅ done · `ClaudeLlm` adapter written and tested with a fake client, **not yet run against the live API** · pgvector/BM25 RAG pending |
| 0 | Postgres RLS, persistence, compose, CI | ✅ done and tested live (RLS, restart survival, per-tenant audit chain) |
| 5 | Labour Form A/B · e-MOA / e-AOA · Form 16 | ✅ done on synthetic samples · parsing is for labelled text, not arbitrary PDF layouts; legal text needs CA/CS review |
| 6b | Next.js CA workbench · mock portal UI | 🟡 workbench + Tally Assistant built; Tally Assistant is wired to the API, the client matrix is still mock data · portal UI todo |
| 8 | Tally Assistant | ✅ verified on a real TallyPrime 7.2 (Education mode) · AI assist built, **not yet run against the live Claude API** |
| 9 | Books from your notebook (single entry to double entry) | ✅ verified: hand-computed cases, simulated shops, production, and ledger-by-ledger against a real Tally |
| 7 | Live GSP / ERI integration | 🟡 **GST via a GSP is built** (login with the taxpayer's OTP, save GSTR-1/3B drafts, never files; simulator-tested, **not verified against a real GSP**). **ERI (income tax) is not built**: its API spec is only issued to registered ERIs. Sessions are stored sealed in Postgres (migration 0007) and the approval OTP is delivered by webhook, never echoed in live mode. Sandbox runbook: `scripts/gsp_sandbox_check.py`. See [`docs/GSP.md`](docs/GSP.md) |
| 10 | Owner view (EN/HI/KN, read-aloud) and impact model | ✅ built on demo data · Hindi and Kannada pending native review |

**Known limitations — stated plainly**

* Agents default to a deterministic **stub** model. `ClaudeLlm` (vision + JSON-schema extraction) exists but has only been tested with a fake client; it needs an API key and a real-bill evaluation before anyone relies on it.
* The workbench's client matrix and owner view run on generated mock data. The Tally Assistant and Books pages talk to the API.
* The live Tally tests (`tests/live`) need TallyPrime installed locally; it is not part of the repository.
* Postgres persistence is opt-in. Production on Vercel uses Neon; tenants are created through an admin-key endpoint (migration 0004 adds its audit action) and sign-in is the temporary admin-key token endpoint until real OTP login exists.
* The Tally XML shape follows Tally's import format but is **unverified** against a live TallyPrime.
* The HSN rate table is intentionally empty (returns `NOT_FOUND`) rather than guessing rates.
* The report's settlement example is internally inconsistent (₹2,370 of deductions against a quoted ₹97,820 credit); the engine follows the arithmetic (₹97,630).
* The §17(5) blocked-credit check is a heuristic until a CA signs off the full HSN list.

---

<sub>**Not tax or legal advice.** This is a hackathon-grade reference implementation. All rates, thresholds, section references and
templates must be verified by a practising Chartered Accountant before any real-world use. No real filing is ever made by this software.</sub>
