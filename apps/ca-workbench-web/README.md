# TaxSetu CA Workbench

A standalone Next.js 15 / React 19 exception matrix for Demo CA Associates and 80 deterministic MSME clients. Plain CSS supports system light/dark themes and horizontally scrollable tables on small screens.

Requires Node 22.18+ (Node 24 recommended).

```sh
npm install
npm run dev
npm test
npm run typecheck
npm run build
npm start
```

Open http://localhost:3000. Search, batch filters and sortable columns operate locally. In Ready to File, Request client OTP queues only visible, previously unrequested ready clients. Counts follow the search. State resets on refresh or route navigation; nothing is persisted or transmitted.

**Safety:** this console cannot file, submit or sign a return. Clients approve and file themselves using their own OTP. The OTP action is simulated and sends nothing.

All clients, GSTIN-shaped identifiers (unvalidated checksum), invoices, adjustment flags, cash coverage and liabilities are fictional. October 2026 activity and a fixed 18 November demo clock keep hydration and priority ordering deterministic. QRMP deadlines are illustrative. Exceptions count non-exact invoices, Rule 37 and RCM flags, and one invoice-linked cash alert separately. Net GST liability is a mock figure, not a tax computation.

Tally XML is generated in the browser from register values and downloaded as a Blob. Each invoice has purchase and input GST debits and a balancing vendor credit. The XML shape and generic ledger names are **unverified against live TallyPrime**: validate mapping in a test company. No import is performed by this app. All monetary arithmetic uses integer paise; formatting supplies an exact decimal string to Intl.NumberFormat.

`lib/api.ts` exposes the unused `NEXT_PUBLIC_API_BASE` placeholder; there is no backend wiring, authentication or real client data. Tests use Node's built-in runner and strip-types in a single process for restricted sandboxes; no test dependency is required.

Implementation environment: `npm install` was attempted, but registry access was blocked (`ENOTCACHED`, then `ECONNREFUSED`). The five pure-helper/data tests pass on Node 24. Build, typecheck and browser verification must be run after installing dependencies in a network-enabled environment.
