# TaxSetu AI

WhatsApp-first agentic compliance co-pilot for Indian micro-enterprises (GST, TDS, e-Way Bill, presumptive ITR, refunds)
and a CA multi-client workbench. Agents **prepare**; a human OTP/DSC token is required to **file** (mock portal in this build).

- Plan & status: [docs/PLAN.md](docs/PLAN.md)
- `packages/deterministic-tax-engine` — zero-LLM Decimal math (GST, TDS, ITR, 44AD, refunds, reconciliation)
- `apps/api-gateway` — FastAPI edge + HITL non-repudiation gate
- `apps/mock-gov-portals` — simulated GSTN / NIC / ITD / MCA endpoints
- `apps/ca-workbench-web` — Next.js CA console
- `packages/agents`, `packages/mcp-servers`, `packages/statutory-rag` — orchestration layer

Not tax advice: all rates/thresholds must be verified by a practising CA before real use.
