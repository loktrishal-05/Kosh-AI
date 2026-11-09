"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "../../lib/tallyApi";
import { booksApi, type Conversion, type SavedBook, type SavedEntry } from "../../lib/booksApi";
import { formToBook, money, type BooksForm } from "../../lib/booksFlow";
export function ConnectedBooks({ token, form, onOpen, onReport, busy, run }: { token: string; form: BooksForm; onOpen: (book: SavedBook, keepEntries?: boolean) => void; onReport: (r: Conversion) => void; busy: boolean; run: (action: () => Promise<string>) => Promise<void> }) {
  const [books, setBooks] = useState<SavedBook[]>([]), [active, setActive] = useState<SavedBook>();
  const [entries, setEntries] = useState<SavedEntry[]>([]), [includeVoid, setIncludeVoid] = useState(false);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [closeReview, setCloseReview] = useState(false), [company, setCompany] = useState("");
  const [acceptTallyReview, setAcceptTallyReview] = useState(false);
  const [staged, setStaged] = useState<{ batch_id: string; what: string; status: string }[]>([]);
  const [nextBook, setNextBook] = useState<SavedBook>();
  const [loadError, setLoadError] = useState("");
  useEffect(() => { let live = true; booksApi.list(token).then(r => { if (live) setBooks(r.books); }).catch(e => { if (live) setLoadError(e.message); }); return () => { live = false; }; }, [token]);
  async function refreshList() { setBooks((await booksApi.list(token)).books); setLoadError(""); }
  async function open(id: string, include = includeVoid) {
    const b = await booksApi.get(id, token);
    const [rows, report] = await Promise.all([booksApi.entries(id, token, include), booksApi.report(id, token)]);
    setActive(b); setEntries(rows.entries); onOpen(b); onReport(report.report); setCloseReview(false); setStaged([]); setNextBook(undefined); setReasons({});
  }
  async function refreshReport() { if (active) { const r = await booksApi.report(active.book_id, token); onReport(r.report); setEntries((await booksApi.entries(active.book_id, token, includeVoid)).entries); } }
  async function close(accept: boolean) {
    if (!active) return "Choose a book first.";
    if (form.entries.length) throw new Error("Add the new notebook lines to this book before closing, or remove them.");
    try { const r = await booksApi.close(active.book_id, accept, token); const b = { ...active, status: "CLOSED" as const }; setActive(b); onOpen(b); onReport(r.report); setCloseReview(false); await refreshList(); return "This period is closed. Its lines and figures are read-only."; }
    catch (e) { setCloseReview(e instanceof ApiError && e.status === 409); throw e; }
  }
  return <section className="panel tally-step" id="my-books"><h2>My books - kept over time</h2><p>Signed in. You can add lines with your business account. Changing figures, voiding, closing, starting a period and staging for Tally require the owner or accountant role.</p><p aria-live="polite">{loadError}</p><button disabled={busy} onClick={() => void run(async () => { await refreshList(); return "Book list refreshed."; })}>Refresh my books</button>
    <ul className="tally-list">{books.map(b => <li key={b.book_id}><strong>{b.name}</strong> | {b.entity_type === "nonprofit" ? "Club or charity" : b.entity_type} | {b.period_start} to {b.period_end} <span className="chip neutral">{b.status === "CLOSED" ? "Closed - read-only" : "Open"}</span> <button disabled={busy} onClick={() => void run(async () => { await open(b.book_id); return "Book opened. The notebook above is empty and ready for new lines; saved lines appear below."; })}>Open {b.name}</button></li>)}</ul>
    {!active && <button disabled={busy} onClick={() => void run(async () => {
      const { entries: lines, ...book } = formToBook(form);
      const created = await booksApi.create(book, token);
      setActive(created); onOpen(created, true);
      let message = "Book created with no notebook lines.";
      if (lines.length) {
        let added;
        try { added = await booksApi.add(created.book_id, lines, "", token); }
        catch (e) { throw new Error(`Book created, but its lines were not added: ${(e as Error).message}. Your lines remain in the notebook; use Add lines to retry.`); }
        onOpen(created);
        message = `Book saved: ${added.added} lines added. ${added.errors.join("; ")}`;
      }
      await refreshList(); await open(created.book_id); return message;
    })}>Save these books</button>}
    {active && <><h3>{active.name} <span className="chip neutral">{active.status === "CLOSED" ? "Closed - read-only" : "Open"}</span></h3><p>Use the notebook and CSV editor above for new lines. Use the opening and year-end fields above to change the figures, then save those changes below.</p><div className="tally-actions"><button disabled={busy} onClick={() => void run(async () => { await open(active.book_id); return "Saved book and report refreshed. Unsaved edits cleared."; })}>Reload saved report</button><button disabled={busy || active.status === "CLOSED" || !form.entries.length} onClick={() => void run(async () => { const lines = formToBook(form).entries; const r = await booksApi.add(active.book_id, lines, "", token); onOpen(active); await open(active.book_id); return `${r.added} lines added. ${r.errors.join("; ")}`; })}>Add lines to this book</button><button disabled={busy || active.status === "CLOSED"} onClick={() => void run(async () => { const b = formToBook(form); const updated = await booksApi.setup(active.book_id, b.opening, b.closing, token); setActive(updated); await refreshReport(); return "Opening and year-end figures saved."; })}>Change opening / year-end figures</button></div>
      <label className="tally-checkbox"><input type="checkbox" checked={includeVoid} disabled={busy} onChange={e => { const include = e.target.checked; void run(async () => { const r = await booksApi.entries(active.book_id, token, include); setIncludeVoid(include); setEntries(r.entries); return include ? "Showing active and voided lines." : "Showing active lines."; }); }} />Include voided lines - corrected records retained for history</label>
      <ul className="tally-list">{entries.map((e, i) => <li key={e.entry_id}><div className={(e.status === "VOID") ? "books-voided" : ""}>{e.date} | {e.description} | In {money(e.receipt || "0")} / Out {money(e.payment || "0")} | {e.mode} | {e.party}</div>{(e.status === "VOID") ? <p>Voided - removed from calculations. Reason: {e.void_reason}</p> : <form onSubmit={event => { event.preventDefault(); void run(async () => { await booksApi.void(active.book_id, e.entry_id, reasons[e.entry_id].trim(), token); await refreshReport(); return "Line voided; the original and reason stay in the history."; }); }}><label>Reason to void line {i + 1}<input required minLength={3} maxLength={200} disabled={busy || active.status === "CLOSED"} value={reasons[e.entry_id] || ""} onChange={event => setReasons({ ...reasons, [e.entry_id]: event.target.value })} /></label><button disabled={busy || active.status === "CLOSED" || (reasons[e.entry_id] || "").trim().length < 3}>Void line {i + 1}</button></form>}</li>)}</ul>
      <div className="tally-actions"><button disabled={busy || active.status === "CLOSED"} onClick={() => void run(() => close(false))}>Close this period</button>{closeReview && active.status === "OPEN" && <button disabled={busy} onClick={() => void run(() => close(true))}>Close anyway, I have reviewed the questions</button>}<button disabled={busy || active.status !== "CLOSED"} onClick={() => void run(async () => { const b = await booksApi.rollover(active.book_id, token); setNextBook(b); await refreshList(); return "Next period created with balances carried forward."; })}>Start next period</button></div>
      {nextBook && <p><a href="#my-books" onClick={e => { e.preventDefault(); void run(async () => { await open(nextBook.book_id); return "Next period opened."; }); }}>Open next period: {nextBook.period_start} to {nextBook.period_end}</a></p>}
      <form onSubmit={e => { e.preventDefault(); void run(async () => { const r = await booksApi.tally(active.book_id, company.trim(), acceptTallyReview, token); setStaged(r.staged); return r.note; }); }}><label>Company name exactly as shown in Tally<input required maxLength={120} value={company} disabled={busy} onChange={e => setCompany(e.target.value)} /></label><label className="tally-checkbox"><input type="checkbox" checked={acceptTallyReview} disabled={busy} onChange={e => setAcceptTallyReview(e.target.checked)} />I have reviewed any unclear lines and questions before sending</label><button disabled={busy || !company.trim()}>Send to Tally</button></form><p>Nothing reaches Tally until approved on the <Link href="/tally">Tally Assistant page</Link>.</p><ul>{staged.map(s => <li key={s.batch_id}>{s.what}: {s.status} | Batch {s.batch_id}</li>)}</ul>
    </>}
  </section>;
}
