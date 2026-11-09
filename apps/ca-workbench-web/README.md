# TaxSetu CA Workbench

A standalone Next.js 15 / React 19 exception matrix for Demo CA Associates and 80 deterministic MSME clients. Plain CSS supports system light/dark themes and horizontally scrollable tables on small screens.

Requires Node 24+.

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

`lib/api.ts` exposes the unused `NEXT_PUBLIC_API_BASE` placeholder for the client matrix. Tests use Node's built-in runner and strip-types in a single process for restricted sandboxes; no test dependency is required.

## Tally Assistant

Open `/tally` to set up suggested ledgers, describe transactions, review bank CSV rows (up to 500 KB), and collect a batch. Demo mode uses anonymous sandbox routes and downloads XML for Tally's Import Data > Vouchers. The sample statement has ten fictional rows. Setup XML is downloaded for the company name entered in step 1.

Connected mode uses temporary admin sign-in with a tenant id and the server's admin key to mint an OWNER token. Only the token is kept in sessionStorage; the admin key is cleared immediately. Entries and setup are staged for explicit approval of their content hash. The local Python bridge in `apps/tally-bridge` collects approved batches; the browser never calls a Tally port. Batch status is checked every five seconds for up to ten minutes. Pairing codes are single use and expire in fifteen minutes.

Browser requests use same-origin `/api/…` URLs. Set the server-side `TAXSETU_API` environment variable to the gateway origin (for example `http://localhost:8000`); it defaults to `https://taxsetu-ai.vercel.app`. Restart/rebuild Next.js after changing it. The connected gateway needs `TAXSETU_ADMIN_KEY` configured and an existing tenant. Live Tally XML imports remain unverified; review entries in a test company first.

Verified locally: `npm test` (13 tests), `npm run typecheck` (strict), and `npm run build` (85 static pages). The new Tally Assistant has not been exercised in a browser or against a live gateway/TallyPrime in this offline worktree.

## Books from your notebook

Open `/books` to try business, club/charity or personal notebook examples, enter opening and year-end figures, import CSV and turn money-in/money-out lines into proper accounts. Results explain the journal, statements, ledgers, trial balance and independent checks; download the journal as CSV. Amounts stay exact decimal strings with BigInt paise totals.

Sign in on `/tally` to share this tab?s session. Saved books support adding lines, voiding with a reason, updating figures, closing and carrying balances into the next period. Owner/CA permissions are required for decisions. Closed books are read-only. Sending to Tally stages batches for separate approval in Tally Assistant; nothing is filed.

The converter source is absent in this worktree. Report types follow `books_routes.py` and `test_single_entry_acceptance.py`: `statements`, `journal` (date/source/narration/lines/flags), `ledgers`, `trial_balance`, `crosscheck`, `counts`, `questions`, `warnings`, `errors`. The sample documentation under `docs/` is outside this UI-only change. Hand-computed sample expectations: business_textbook sales 770,000.00, purchases 381,500.00, gross profit 403,500.00, net profit 211,000.00, assets 354,000.00; nonprofit_club income 100,000.00, expenditure 89,800.00, surplus 10,200.00, closing fund 102,200.00; individual_freelancer income 496,000.00, expenses 368,000.00, savings 128,000.00, net worth at cost 241,000.00 and at market 256,000.00. Kirana is a full year of shop transactions including credit customers, suppliers, a loan, an asset and bad debt.
