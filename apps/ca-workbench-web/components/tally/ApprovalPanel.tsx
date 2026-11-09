"use client";
import { useEffect, useRef, useState } from "react";
import { tallyApi, type Batch } from "../../lib/tallyApi";
import { flagMessage, paise, rupees } from "../../lib/tallyFlow";

export function batchStatus(batch: Batch): string {
  switch (batch.status) {
    case "PENDING_APPROVAL": return "Waiting for your approval";
    case "APPROVED": return "Approved - your Tally bridge will post it within about a minute";
    case "POSTED": return `Posted to Tally (created ${batch.ack?.created ?? 0})`;
    case "FAILED": return `Tally refused it: ${batch.ack?.errors?.join("; ") || "No error details returned. Check your bridge."}`;
    case "REJECTED": return "Rejected - this batch will not be sent to Tally";
  }
}
export function ApprovalPanel({ token, batch, onBatch }: { token: string; batch: Batch | null; onBatch: (batch: Batch) => void }) {
  const [history, setHistory] = useState<Batch[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [pollMessage, setPollMessage] = useState("");
  const result = useRef<HTMLDivElement>(null);
  const final = !!batch && ["POSTED", "FAILED", "REJECTED"].includes(batch.status);
  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await action(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update the batch. Try again."); }
    finally { setBusy(false); requestAnimationFrame(() => result.current?.focus()); }
  }
  async function refresh() { setHistory((await tallyApi.batches(token)).batches); }
  useEffect(() => {
    let active = true;
    setBusy(true);
    tallyApi.batches(token).then(r => { if (active) setHistory(r.batches); }).catch(e => { if (active) setMessage(e.message); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [token]);
  useEffect(() => {
    setPollMessage("");
    if (!batch || final) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const deadline = setTimeout(() => {
      controller.abort(); clearTimeout(timer);
      setPollMessage("Automatic checking stopped after 10 minutes. Refresh the batch to check again.");
    }, 600_000);
    async function poll() {
      try {
        const updated = await tallyApi.batch(batch!.batch_id, token, controller.signal);
        if (controller.signal.aborted) return;
        onBatch(updated); setPollMessage("");
        if (["POSTED", "FAILED", "REJECTED"].includes(updated.status)) return;
      } catch (error) {
        if (controller.signal.aborted) return;
        setPollMessage(error instanceof Error ? error.message : "Could not check the batch.");
      }
      timer = setTimeout(poll, 5000);
    }
    timer = setTimeout(poll, 5000);
    return () => { controller.abort(); clearTimeout(timer); clearTimeout(deadline); };
  }, [batch?.batch_id, token, onBatch, final]);
  return <div className="tally-subpanel"><h3>Approval and delivery</h3>
    <div ref={result} tabIndex={-1} aria-live="polite"><p role="status">{message}</p>{batch && <>
      <p>Company: <strong>{batch.company}</strong> · {batch.kind === "masters" ? "Tally setup" : "Book entries"}</p>
      <p className="tally-code">Batch id: {batch.batch_id}</p><p>Content hash: <code>{batch.sha256.slice(0, 12)}</code>. You are approving exactly this content.</p>
      <ul>{batch.summary.items.map((item, index) => <li key={index}>{item.name ? `${item.name} (${item.parent})` : `${item.date} · ${item.party || item.vtype} · ${item.amount ? rupees(paise(item.amount)) : ""}`}{item.flags?.map(flag => <small key={flag}>{flagMessage(flag)}</small>)}</li>)}</ul>
      <p className="chip neutral">{batchStatus(batch)}</p><p>{pollMessage}</p>
      <div className="tally-actions"><button disabled={busy || batch.status !== "PENDING_APPROVAL"} onClick={() => run(async () => { const r = await tallyApi.approve(batch.batch_id, batch.sha256, token); onBatch({ ...batch, status: r.status }); await refresh(); })}>Approve</button>
      <button disabled={busy || batch.status !== "PENDING_APPROVAL"} onClick={() => run(async () => { const r = await tallyApi.reject(batch.batch_id, token); onBatch({ ...batch, status: r.status }); await refresh(); })}>Reject</button>
      <button disabled={busy} onClick={() => run(async () => { onBatch(await tallyApi.batch(batch.batch_id, token)); await refresh(); })}>Refresh batch status</button></div>
    </>}</div>
    <details><summary>Previously staged batches</summary><button disabled={busy} onClick={() => run(refresh)}>Refresh batch list</button>{history.length ? <ul>{history.map(item => <li key={item.batch_id}><button disabled={busy} onClick={() => run(async () => onBatch(await tallyApi.batch(item.batch_id, token)))}>{item.company} · {item.summary.count} items · {batchStatus(item)} · {item.batch_id.slice(0, 8)}</button></li>)}</ul> : <p>{busy ? "Loading batches…" : "No batches found. Stage entries or setup to begin."}</p>}</details>
  </div>;
}
