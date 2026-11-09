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
| 0 | Monorepo, Docker Compose, migrations with RLS | `tests/infra/test_rls_isolation.py` | **done**: schema + compose + RLS verified live; Postgres-backed drafts and per-tenant audit chain (migration 0002); CI runs the DB tests against a service container |
| 1 | **Deterministic engine**: GSTIN Mod-36, GST split, §17(5), TDS 194C/J/H/Q, ITR router, 44AD/ADA/AE, 87A, regimes, refund pathways, Rule 37, 4-way 2B match | 250+ parameterized tests, 100% | **done (182 tests)** |
| 2 | MCP server mesh (8 servers; start with gstn-nic mock, tally-xml, statutory-rag, incometax) | tools/list + tools/call tests | **done (mock backends)** - 7 working servers, mca-labour registered but its 3 generators refuse until Phase 5; stdio JSON-RPC, no filing tool can be registered; 25 tests |
| 3 | 5 agents + effective-dated statutory RAG (LLM calls behind an interface; stubbed offline) | agent eval + loop-cap tests | **done offline** - 5 graph agents, StubLlm, keyword RAG with 2 effective-dated versions; real LLM adapter + pgvector/BM25 still todo; 24 tests |
| 4 | Payment drawer: 3-way split, GST escrow, 22-field receipt, 5-ledger posting | split/ledger invariant tests | **core logic done** (split, trust score, balanced ledgers, Tally XML, MDR unbundling); UPI rails/UI + 22-field receipt todo |
| 5 | e-MOA/e-AOA, Form 16 A/B, Labour Form A/B | generator tests | **done on synthetic samples**: Labour Form A/B, Form 16 parser + validator, e-MOA (INC-33) / e-AOA (INC-34) drafters, all wired as `mca-labour` MCP tools (draft-only; CA/CS review required) |
| 6a | HITL gate + mock portal + audit chain + FastAPI gateway (REST, WhatsApp HMAC webhook, JWT roles) | air-gap + e2e demo tests | **done (21 tests)** |
| 6b | Mock gov-portal UI + CA workbench (Next.js) | e2e demo | **partial**: CA workbench built by Codex (matrix, 2B diff, Tally export; typecheck, build and 5 unit tests pass) on mock data, not yet wired to the API; portal UI todo |
| 7 | Production hardening, live GSP/ERI | out of scope (needs licensed credentials) | deferred |
| 8 | Tally Assistant (see `docs/TALLY.md`) | books engine, classifier, bank importer, bridge, approval outbox, UI | **built; verified on a real TallyPrime 7.2 (Education)**; other Tally versions, UTF-16 names, real login pending |

## Build order & cadence
Phase 0 → 1 → 6 (gate + mock portals) → 2/3 → 4/5 → workbench UI. Each phase ends with passing tests, a commit and a push.
Small, self-contained chores (fixtures, boilerplate, extra test tables) may be delegated to Codex CLI.

## Out of scope / needs external input
Live GSP/ERI/NIC credentials, real WhatsApp (Meta WABA) tokens, real LLM API keys, Class-3 DSC bridge, Account Aggregator.
These are wired behind interfaces and env vars (`.env.example`) with offline stubs so everything runs and tests locally.

## Known issues in the source report
- Part III s2.2 settlement example: bank credit Rs 97,820 vs deductions 1,500+270+500+100 = 2,370 (would be Rs 97,630). Engine follows the arithmetic.
- Tally XML is built to Tally's documented import shape but has not been tested against a live TallyPrime.
- Tax rates/thresholds (e.g. 194H, slabs) are the report's and AY 2026-27 slabs; re-verify with a CA, especially post Income-tax Act 2025.

## Statutory caveat
Rates, thresholds and dates come from the report and must be re-verified by a practising CA before any real use.
