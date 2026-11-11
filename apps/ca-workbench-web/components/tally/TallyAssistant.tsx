"use client";
import { useEffect, useRef, useState } from "react";
import { tallyApi, type AiStatus, type Batch, type Draft, type Entry, type Ledger, type Pack, type Setup, type Staged, type Statement } from "../../lib/tallyApi";
import { bankNeedsCheck, batchTotals, clearToken, flagMessage, getToken, paise, rupees, sampleBankCsv, setLedger, setToken } from "../../lib/tallyFlow";
import { escapeXml } from "../../lib/tally";
import { ApprovalPanel } from "./ApprovalPanel";
import { BillReader } from "./BillReader";
import { BridgePanel } from "./BridgePanel";

const states = [
  ["01", "Jammu and Kashmir"], ["02", "Himachal Pradesh"], ["03", "Punjab"], ["04", "Chandigarh"], ["05", "Uttarakhand"], ["06", "Haryana"], ["07", "Delhi"], ["08", "Rajasthan"], ["09", "Uttar Pradesh"], ["10", "Bihar"], ["11", "Sikkim"], ["12", "Arunachal Pradesh"], ["13", "Nagaland"], ["14", "Manipur"], ["15", "Mizoram"], ["16", "Tripura"], ["17", "Meghalaya"], ["18", "Assam"], ["19", "West Bengal"], ["20", "Jharkhand"], ["21", "Odisha"], ["22", "Chhattisgarh"], ["23", "Madhya Pradesh"], ["24", "Gujarat"], ["26", "Dadra and Nagar Haveli and Daman and Diu"], ["27", "Maharashtra"], ["29", "Karnataka"], ["30", "Goa"], ["31", "Lakshadweep"], ["32", "Kerala"], ["33", "Tamil Nadu"], ["34", "Puducherry"], ["35", "Andaman and Nicobar Islands"], ["36", "Telangana"], ["37", "Andhra Pradesh"], ["38", "Ladakh"],
];
const examples = ["Paid 25000 rent to Sharma by cheque yesterday", "Received 40k from Rao Traders by UPI", "Bought goods 50000 plus 18% GST from Gupta Traders", "Paid 18000 salary by bank", "Withdrew 5000 from bank for cash"];
const glossary = {
  Ledger: "A named place in your books for one kind of money or activity, such as rent, cash or a customer. A Tally group collects similar ledgers together.",
  Voucher: "One recorded transaction in Tally, such as a payment or a sale.",
  Debit: "One side of a book entry. It usually increases cash, things you own or costs, and reduces money you owe or income.",
  Credit: "The other side of a book entry. It usually reduces cash, things you own or costs, and increases money you owe or income. Every entry has equal debit and credit totals.",
  GSTIN: "The 15-character identification number of a business registered for Goods and Services Tax (GST). Check a supplier's number on their bill.",
  ITC: "Input tax credit: GST you paid on eligible business purchases that may reduce the GST you owe. Some purchases cannot qualify.",
  TDS: "Tax deducted at source: tax you may need to hold back from certain payments and pay to the government.",
  Bridge: "The small program on your Tally computer that collects approved entries from Kosh AI and sends them to Tally.",
};
const suspense = (draft: Draft) => draft.lines.some(line => line.ledger === "Suspense A/c");
const needsCheck = bankNeedsCheck;
const rowLedger = (draft: Draft) => draft.lines.find(line => line.ledger !== "Bank Account")?.ledger ?? draft.lines[0]?.ledger ?? "";
function download(xml: string, filename: string) {
  const url = URL.createObjectURL(new Blob([xml], { type: "application/xml;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function AiChip({ ai }: { ai?: AiStatus }) { return ai ? <p><span className="chip neutral">{ai.enabled ? "AI assist is on" : ai.note}</span></p> : null; }
function Flags({ flags }: { flags: string[] }) { return flags.length ? <ul className="tally-flags">{[...new Set(flags)].map(flag => <li key={flag}>{flagMessage(flag)}</li>)}</ul> : <p>No additional checks flagged. Review the details before adding.</p>; }
function DraftTable({ draft }: { draft: Draft }) {
  return <><p>Debit and credit are the two sides of each record. Debit usually raises cash or costs; credit usually lowers cash or raises income or money owed. See the glossary below.</p><div className="table-region" tabIndex={0} role="region" aria-label="What Tally will record"><table><caption>What Tally will record</caption><thead><tr><th scope="col">Ledger (category)</th><th scope="col">Goes up or down</th><th scope="col">Amount</th></tr></thead><tbody>{draft.lines.map((line, index) => <tr key={index}><td>{line.ledger}</td><td>{line.side === "Dr" ? "Debit — cash/costs up, money owed/income down" : "Credit — cash/costs down, money owed/income up"}</td><td>{rupees(paise(line.amount))}</td></tr>)}</tbody></table></div></>;
}
export function TallyAssistant() {
  const [mode, setMode] = useState<"demo" | "connected">("demo");
  const [token, updateToken] = useState("");
  const [tenant, setTenant] = useState("");
  const adminKey = useRef<HTMLInputElement>(null);
  const [setup, setSetup] = useState<Setup>({ company: "", business_type: "trader", state_code: "29" });
  const [pack, setPack] = useState<Pack | null>(null);
  const [packBusy, setPackBusy] = useState(false);
  const [packError, setPackError] = useState("");
  const [packVersion, setPackVersion] = useState(0);
  const [knownLedgers, setKnownLedgers] = useState<Ledger[]>([]);
  const [text, setText] = useState("");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [statement, setStatement] = useState<Statement | null>(null);
  const [remember, setRemember] = useState<Record<number, boolean>>({});
  const [batch, setBatch] = useState<Draft[]>([]);
  const [selected, selectBatch] = useState<Batch | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const result = useRef<HTMLDivElement>(null);
  const entryResult = useRef<HTMLDivElement>(null);
  const bankResult = useRef<HTMLDivElement>(null);
  const auth = mode === "connected" ? token : undefined;
  const locked = busy || (mode === "connected" && !token);
  const total = batchTotals(batch);
  const bankTotals = batchTotals(statement?.drafts ?? []);
  const ready = statement?.drafts.filter(d => !needsCheck(d)) ?? [];
  const companyValid = !!setup.company.trim();
  useEffect(() => { updateToken(getToken()); }, []);
  useEffect(() => {
    let active = true;
    setPackBusy(true); setPack(null); setPackError("");
    tallyApi.starterPack(setup.business_type, setup.state_code).then(r => { if (active) setPack(r); }).catch(e => { if (active) setPackError(e.message); }).finally(() => { if (active) setPackBusy(false); });
    return () => { active = false; };
  }, [setup.business_type, setup.state_code, packVersion]);
  useEffect(() => {
    if (!auth) { setKnownLedgers([]); return; }
    let active = true;
    tallyApi.ledgers(auth).then(r => { if (active) setKnownLedgers(r.ledgers); }).catch(e => { if (active) { setMessage(`Could not load your Tally ledgers: ${e.message}. Starter categories remain available; sign in again if your token expired.`); setError(true); } });
    return () => { active = false; };
  }, [auth]);
  async function run(action: () => Promise<string>, focus = result) {
    setBusy(true); setMessage(""); setError(false);
    try { setMessage(await action()); }
    catch (error) { setError(true); setMessage(error instanceof Error ? error.message : "Something went wrong. Please try again."); focus = result; }
    finally { setBusy(false); requestAnimationFrame(() => focus.current?.focus()); }
  }
  function clearWork() {
    setText(""); setEntry(null); setStatement(null); setBatch([]); selectBatch(null); setRemember({}); setMessage(""); setError(false);
  }
  function changeMode(next: "demo" | "connected") {
    if (next === mode) return;
    setMode(next); clearWork();
  }
  function staged(result: Staged) {
    selectBatch({ batch_id: result.batch_id, sha256: result.payload_sha256, status: result.status, summary: result.summary, company: setup.company.trim(), kind: "vouchers" });
  }
  async function readStatement(csv: string) {
    if (!csv.trim()) throw new Error("The statement is empty. Choose a CSV with transaction rows.");
    if (new Blob([csv]).size > 500 * 1024) throw new Error("Choose a CSV no larger than 500 KB.");
    const response = await tallyApi.statement(csv, setup.state_code, auth);
    setStatement(response); setRemember({});
    return `${response.drafts.length} statement rows prepared. Check the categories below.`;
  }
  function addDrafts(drafts: Draft[]) {
    if (batch.length + drafts.length > 500) throw new Error("A batch can contain at most 500 entries. Send or remove some entries first.");
    setBatch(current => [...current, ...drafts]);
  }
  const options = [...new Set([...(pack?.ledgers ?? []), ...knownLedgers].map(l => l.name))];
  return <div className="tally-assistant">
    <section className="page-heading"><div><p className="eyebrow">YOUR EVERYDAY BOOKS</p><h1>Tally Assistant<span className="title-dot">.</span></h1><p className="muted">Tell us what happened. Check the draft. Decide what reaches your books.</p></div><span className="chip neutral">Current mode: {mode === "demo" ? "Demo (no sign-in)" : "Connected"}</span></section>
    <section className="panel tally-step" aria-labelledby="mode-title"><h2 id="mode-title">Choose how to work</h2><div className="tally-actions" aria-label="Assistant mode"><button disabled={busy} aria-pressed={mode === "demo"} onClick={() => changeMode("demo")}>Demo (no sign-in)</button><button disabled={busy} aria-pressed={mode === "connected"} onClick={() => changeMode("connected")}>Connected</button></div><p>{mode === "demo" ? "Try sample or your own transactions. Nothing is saved to an account. Finish by downloading a Tally file." : "Use your business account to stage and approve entries for your Tally bridge."} Switching mode clears unsent entries on this page.</p>
      {mode === "connected" && (!token ? <form onSubmit={e => { e.preventDefault(); const key = adminKey.current?.value ?? ""; if (adminKey.current) adminKey.current.value = ""; void run(async () => { const response = await tallyApi.devToken(tenant.trim(), key); setToken(response.token); updateToken(response.token); return "Signed in for this tab. The temporary token lasts up to 12 hours."; }); }}><h3>Temporary admin sign-in</h3><p>Use your tenant id and the server's admin key. We keep only the minted token in this tab's session storage.</p><div className="tally-fields"><label>Tenant id<input required pattern="[0-9a-fA-F\-]{36}" value={tenant} onChange={e => setTenant(e.target.value)} autoComplete="off" disabled={busy} /></label><label>Admin key<input ref={adminKey} type="password" required minLength={24} autoComplete="off" disabled={busy} /></label></div><button className="primary" disabled={busy}>Sign in</button></form> : <div><p>Signed in for this tab as the business owner. Admin key is not retained.</p><button disabled={busy} onClick={() => { clearToken(); updateToken(""); clearWork(); }}>Sign out</button></div>)}
    </section>
    <div className={`tally-notice ${error ? "tally-error" : ""}`} ref={result} tabIndex={-1} aria-live="polite" role="status">{busy ? "Working…" : message}</div>
    <section className="panel tally-step" aria-labelledby="setup-title"><h2 id="setup-title"><span className="tally-number">1</span> Set up your Tally</h2><p>Choose your business details. We suggest ledgers — named categories for your money and activity — grouped the way Tally organises them.</p>
      <div className="tally-fields"><label>Business type<select value={setup.business_type} disabled={busy} onChange={e => setSetup({ ...setup, business_type: e.target.value as Setup["business_type"] })}><option value="trader">Trader — buy and sell goods</option><option value="service">Service — work for customers</option><option value="manufacturer">Manufacturer — make goods</option></select></label><label>Business state<select value={setup.state_code} disabled={busy} onChange={e => setSetup({ ...setup, state_code: e.target.value })}>{states.map(([code, state]) => <option key={code} value={code}>{state} ({code})</option>)}</select></label><label>Company name in Tally<input maxLength={120} value={setup.company} disabled={busy} onChange={e => setSetup({ ...setup, company: e.target.value })} placeholder="Exactly as shown in Tally" /></label></div>
      <div aria-live="polite">{packBusy && <p>Loading suggested ledgers…</p>}{packError && <p>{packError} <button disabled={packBusy} onClick={() => setPackVersion(v => v + 1)}>Retry suggested ledgers</button></p>}{pack && (!pack.ledgers.length ? <p>No suggested ledgers returned. Try another business type.</p> : <details><summary>See {pack.ledgers.length} suggested ledgers and what they mean</summary>{[...new Set(pack.ledgers.map(l => l.parent))].map(group => <div key={group}><h3>{group} <small>Tally group — a collection of related categories</small></h3><dl>{pack.ledgers.filter(l => l.parent === group).map(ledger => <div key={ledger.name}><dt>{ledger.name}</dt><dd>{ledger.meaning || "A category for this business activity. Ask your accountant if you are unsure where it belongs."}</dd></div>)}</dl></div>)}</details>)}</div>
      <div className="tally-actions"><button disabled={busy || !pack || !companyValid} onClick={() => run(async () => { download(pack!.xml.replace(/<SVCURRENTCOMPANY>[^<]*<\/SVCURRENTCOMPANY>/g, () => `<SVCURRENTCOMPANY>${escapeXml(setup.company.trim())}</SVCURRENTCOMPANY>`), "tally-setup.xml"); return "Setup XML downloaded for your company. In Tally, use Import Data > Masters to load these categories."; })}>Download setup file (XML)</button>{mode === "connected" && <button disabled={locked || !companyValid || !pack} onClick={() => run(async () => { const response = await tallyApi.setup({ ...setup, company: setup.company.trim() }, token); if ("nothing_to_do" in response) return "Your Tally already has these ledgers. Nothing to send."; selectBatch({ batch_id: response.batch_id, sha256: response.payload_sha256, status: response.status, summary: response.summary, company: setup.company.trim(), kind: "masters" }); return "Setup staged. Review its categories in step 4 and approve to send."; })}>Send to my Tally</button>}</div><p className="footnote">Use the exact company name before downloading or sending setup. Changing these details does not change entries already drafted.</p>
    </section>
    <section className="panel tally-step" aria-labelledby="entry-title"><h2 id="entry-title"><span className="tally-number">2</span> Tell us what happened</h2><AiChip ai={entry?.ai} /><p>Use ordinary words: who, how much, when, and how you paid. GST means Goods and Services Tax.</p><div className="tally-actions">{examples.map(example => <button className="tally-example" disabled={locked} key={example} onClick={() => { setText(example); setEntry(null); }}>{example}</button>)}</div><label>What happened?<textarea value={text} maxLength={1000} rows={4} disabled={locked} onChange={e => { setText(e.target.value); setEntry(null); }} placeholder="For example: Paid 25000 rent to Sharma by cheque yesterday" /></label><button className="primary" disabled={locked || !text.trim()} onClick={() => run(async () => { setEntry(null); const response = await tallyApi.entry(text.trim(), setup.state_code, auth); setEntry(response); return response.draft ? "Your draft is ready below. Check it before adding." : "We need a little more detail. Answer the questions in your description and try again."; }, entryResult)}>Understand this</button>
      <div ref={entryResult} tabIndex={-1} aria-live="polite">{entry ? <div className="tally-subpanel">{entry.draft ? <><p><strong>{entry.plain || entry.interpretation || "Review this draft entry."}</strong></p><DraftTable draft={entry.draft} /><Flags flags={[...entry.flags, ...entry.draft.flags]} /><button disabled={locked || suspense(entry.draft)} onClick={() => run(async () => { addDrafts([entry.draft!]); setEntry(null); return "Entry added to your batch in step 4."; })}>Add to my batch</button>{suspense(entry.draft) && <p>Suspense A/c means we could not choose a category. Add more detail and try again.</p>}</> : <><h3>A little more detail, please</h3>{entry.questions.length ? <ul>{entry.questions.map(q => <li key={q}>{q}</li>)}</ul> : <p>No draft could be made. Include the amount, person and payment method.</p>}<Flags flags={entry.flags} /></>}</div> : <p className="muted">Your explanation and draft will appear here.</p>}</div>
      {auth && <BillReader token={auth} stateCode={setup.state_code} disabled={busy} onAdd={draft => { addDrafts([draft]); setMessage("Bill added to your batch in step 4."); }} />}
    </section>
    <section className="panel tally-step" aria-labelledby="bank-title"><h2 id="bank-title"><span className="tally-number">3</span> Upload your bank statement</h2><AiChip ai={statement?.ai} /><p>CSV only, up to 500 KB. The file is read in this browser, then its text is sent to Kosh AI for review. Include Date, Narration, Debit (money out), and Credit (money in) columns.</p><label>Bank statement CSV<input type="file" accept=".csv,text/csv" disabled={locked} onChange={e => { const file = e.target.files?.[0]; e.target.value = ""; if (!file) return; void run(async () => { if (!/\.csv$/i.test(file.name)) throw new Error("Choose a CSV file, not a PDF or spreadsheet."); if (file.size > 500 * 1024) throw new Error("Choose a CSV no larger than 500 KB."); return readStatement(await file.text()); }, bankResult); }} /></label><div className="tally-actions"><button disabled={locked} onClick={() => run(() => readStatement(sampleBankCsv), bankResult)}>Use a sample statement</button></div>
      <div ref={bankResult} tabIndex={-1} aria-live="polite">{statement ? <><p>{statement.errors.length ? "Some rows could not be read:" : "Statement read."} Skipped rows: {statement.skipped}.</p>{statement.errors.length > 0 && <ul>{statement.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}<div className="summary">{[["Ready", String(ready.length)], ["Needs your check", String(statement.drafts.length - ready.length)], ["Money in", rupees(bankTotals.moneyIn)], ["Money out", rupees(bankTotals.moneyOut)]].map(([label, value]) => <div className="tile" key={label}><span>{label}</span><strong className="amount">{value}</strong></div>)}</div><p>Suspense A/c is a temporary holding category for a row we could not identify. Choose a real category to make the row ready. You can change any row.</p>
      {statement.drafts.length ? <div className="table-region" tabIndex={0} role="region" aria-label="Bank statement review"><table className="tally-bank"><caption>Review each bank row</caption><thead><tr><th scope="col">Transaction</th><th scope="col">Amount</th><th scope="col">Ledger (category)</th><th scope="col">Check</th></tr></thead><tbody>{statement.drafts.map((draft, index) => { const current = rowLedger(draft); return <tr key={index}><td><strong>{draft.date} · {draft.party || "Bank transaction"}</strong><p>{draft.narration}</p><p>{draft.plain}</p><details><summary>Checks and recorded lines</summary><Flags flags={draft.flags} /><ul>{draft.lines.map((l, i) => <li key={i}>{l.ledger} · {l.side === "Dr" ? "Debit" : "Credit"} · {rupees(paise(l.amount))}</li>)}</ul></details></td><td>{rupees(batchTotals([draft]).total)}</td><td><label>Category for row {index + 1}<select disabled={locked} value={current} onChange={e => { const changed = setLedger(draft, current, e.target.value); setStatement({ ...statement, drafts: statement.drafts.map((d, i) => i === index ? { ...changed, plain: undefined, flags: changed.flags.filter(f => f !== "NEEDS_REVIEW" && !f.startsWith("AI_SUGGESTED")) } : d) }); }} >{[...new Set([...options, current])].map(name => <option key={name}>{name}</option>)}</select></label>{needsCheck(draft) && !suspense(draft) && <button disabled={locked} onClick={() => setStatement({ ...statement, drafts: statement.drafts.map((d, i) => i === index ? { ...d, flags: d.flags.filter(f => f !== "NEEDS_REVIEW" && !f.startsWith("AI_SUGGESTED")) } : d) })}>I checked this category</button>}{mode === "connected" && <label className="tally-checkbox"><input type="checkbox" disabled={locked || !draft.party || draft.party.length > 60 || suspense(draft)} checked={!!remember[index]} onChange={e => setRemember({ ...remember, [index]: e.target.checked })} />Remember this payee</label>}</td><td>{draft.flags.some(f => f.startsWith("AI_SUGGESTED")) && <span className="chip warning">Suggested by AI</span>}{needsCheck(draft) ? "Needs your check" : "Ready — review before adding"}</td></tr>; })}</tbody></table></div> : <p>No transaction rows were found. Check the column headings or try the sample statement.</p>}
      <button className="primary" disabled={locked || !ready.length} onClick={() => run(async () => { if (batch.length + ready.length > 500) throw new Error("A batch can contain at most 500 entries."); if (auth) { for (const [index, draft] of statement.drafts.entries()) { if (remember[index] && !needsCheck(draft)) await tallyApi.alias(draft.party, rowLedger(draft), auth); } } addDrafts(ready); setStatement({ ...statement, drafts: statement.drafts.filter(needsCheck) }); setRemember({}); return `${ready.length} ready rows added to your batch. Any rows needing a category remain above.`; })}>Add ready rows to my batch</button></> : <p className="muted">Choose a CSV or try 10 fictional transactions with the sample button.</p>}</div>
    </section>
    <section className="panel tally-step" aria-labelledby="review-title"><h2 id="review-title"><span className="tally-number">4</span> Review and send</h2><p>{batch.length} entries · Total {rupees(total.total)} · Debit {rupees(total.debit)} / Credit {rupees(total.credit)} (the two sides must match).</p>{batch.length ? <ul className="tally-list">{batch.map((draft, index) => <li key={index}><strong>{draft.date} · {draft.party || draft.vtype} · {rupees(batchTotals([draft]).total)}</strong><p>{draft.plain || draft.narration}</p><details><summary>Review entry {index + 1}</summary><DraftTable draft={draft} /><Flags flags={draft.flags} /></details><button disabled={busy} onClick={() => run(async () => { setBatch(batch.filter((_, i) => i !== index)); return `Entry ${index + 1} removed from your unsent batch.`; })}>Remove<span className="sr-only"> entry {index + 1}</span></button></li>)}</ul> : <p>Your batch is empty. Add a text entry or ready bank rows above.</p>}
      {mode === "demo" ? <><button className="primary" disabled={locked || !batch.length || !companyValid} onClick={() => run(async () => { const response = await tallyApi.voucherXml({ company: setup.company.trim(), drafts: batch }); download(response.xml, "tally-vouchers.xml"); return `Tally file downloaded with ${response.count} entries.`; })}>Download Tally file</button><p>Import this file in Tally via Import Data &gt; Vouchers. Check it in a test company first.</p></> : <><button className="primary" disabled={locked || !batch.length || !companyValid || total.debit !== total.credit} onClick={() => run(async () => { staged(await tallyApi.stage({ company: setup.company.trim(), drafts: batch }, token)); setBatch([]); return "Batch staged below. Review the content, then approve or reject it."; })}>Stage for approval</button>{token && <ApprovalPanel token={token} batch={selected} onBatch={selectBatch} />}</>}{!companyValid && <p>Enter your company name in step 1 to download or send.</p>}
    </section>
    {mode === "connected" && token && <BridgePanel token={token} company={setup.company} />}
    <details className="panel tally-step"><summary>What do these words mean?</summary><dl>{Object.entries(glossary).map(([word, meaning]) => <div key={word}><dt>{word}</dt><dd>{meaning}</dd></div>)}</dl></details>
  </div>;
}
