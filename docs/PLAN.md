# TaxSetu AI — Build Plan & Schedule

Source: *TaxSetu AI Complete Master Report (PS 3.1)*. This file is the working plan; the PDF is not committed.

## What we are building
A WhatsApp-first, multi-agent **pre-filing compliance co-pilot** for Indian micro-enterprises (GST, TDS, e-Way Bill,
presumptive ITR, refunds) plus a **CA multi-client workbench**. Filing is **never autonomous**: agents *stage* drafts, and
only a human OTP/DSC token bound to the SHA-256 of the final JSON unlocks filing (against a **mock** government portal in
the hackathon build).

## Non-negotiable invariants (from the report)
1. **Zero-LLM arithmetic** — all tax/TDS/interest/ITR math is Python `Decimal`; LLMs only extract/classify/draft.
2. **HITL air-gap** — agents have no route/credential to RETFILE / SubmitITR / IMS-reject / payouts (FR-025).
3. **Multi-tenant RLS** — PostgreSQL row-level security keyed on `tenant_id`.
4. **Untrusted-input handling** — OCR text and supplier replies are data, never instructions.
5. **Hard loop caps** — max 3 supplier nudges per invoice per period, 48h cooldown.
6. **Dual-mode gateway** — `MockPortalProvider` (now) / `LiveGSP_ERI_Provider` (later, needs licensed credentials).

## Stack
Python (FastAPI, Pydantic v2, Decimal, pytest) · PostgreSQL 16 + pgvector · Redis · MinIO · Next.js + Tailwind (CA
workbench) · MCP servers (JSON-RPC 2.0) · LangGraph agents. Local Python is 3.10, so code targets `>=3.10`.

## Phases (report Part IV) and status
| # | Phase | Deliverable / gate | Status |
|---|-------|--------------------|--------|
| 0 | Monorepo, Docker Compose, migrations with RLS | `tests/infra/test_rls_isolation.py` | todo |
| 1 | **Deterministic engine**: GSTIN Mod-36, GST split, §17(5), TDS 194C/J/H/Q, ITR router, 44AD/ADA/AE, 87A, regimes, refund pathways, Rule 37, 4-way 2B match | 250+ parameterized tests, 100% | **done (182 tests)** |
| 2 | MCP server mesh (8 servers; start with gstn-nic mock, tally-xml, statutory-rag, incometax) | tools/list + tools/call tests | todo |
| 3 | 5 agents + effective-dated statutory RAG (LLM calls behind an interface; stubbed offline) | agent eval + loop-cap tests | todo |
| 4 | Payment drawer: 3-way split, GST escrow, 22-field receipt, 5-ledger posting | split/ledger invariant tests | todo |
| 5 | e-MOA/e-AOA, Form 16 A/B, Labour Form A/B | generator tests | todo |
| 6 | HITL gate + mock gov portals + CA workbench (Next.js) | air-gap + e2e demo test | todo |
| 7 | Production hardening, live GSP/ERI | out of scope (needs licensed credentials) | deferred |

## Build order & cadence
Phase 0 → 1 → 6 (gate + mock portals) → 2/3 → 4/5 → workbench UI. Each phase ends with passing tests, a commit and a push.
Small, self-contained chores (fixtures, boilerplate, extra test tables) may be delegated to Codex CLI.

## Out of scope / needs external input
Live GSP/ERI/NIC credentials, real WhatsApp (Meta WABA) tokens, real LLM API keys, Class-3 DSC bridge, Account Aggregator.
These are wired behind interfaces and env vars (`.env.example`) with offline stubs so everything runs and tests locally.

## Statutory caveat
Rates, thresholds and dates come from the report and must be re-verified by a practising CA before any real use.
