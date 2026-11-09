"use client";
import { useState } from "react";
import { tallyApi, type Bill, type Draft } from "../../lib/tallyApi";
import { flagMessage, paise, rupees } from "../../lib/tallyFlow";

export function BillReader({ token, stateCode, disabled, onAdd }: { token: string; stateCode: string; disabled: boolean; onAdd: (draft: Draft) => void }) {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File>();
  const [bill, setBill] = useState<Bill>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  async function read() {
    setBusy(true); setNotice(""); setBill(undefined);
    try {
      let image_base64 = "";
      if (file) {
        if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) throw new Error("Choose a JPG, PNG or WebP photo up to 5 MB.");
        image_base64 = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = () => reject(new Error("Could not read this photo. Choose it again.")); reader.readAsDataURL(file); });
      }
      setBill(await tallyApi.readBill({ text, image_base64, media_type: file?.type || "image/jpeg", state_code: stateCode }, token));
    } catch (e) { setNotice(e instanceof Error ? e.message : "Could not read this bill."); }
    finally { setBusy(false); }
  }
  return <div className="tally-subpanel"><h3>Have a supplier bill?</h3><p>Send a photo or paste the words from the paper. Check every figure before adding it.</p>
    <label>Bill photo (JPG, PNG or WebP, up to 5 MB)<input type="file" accept="image/jpeg,image/png,image/webp" disabled={disabled || busy} onChange={e => { setFile(e.target.files?.[0]); setBill(undefined); }} /></label>
    <label>Bill text<textarea rows={4} maxLength={20000} value={text} onChange={e => { setText(e.target.value); setBill(undefined); }} disabled={disabled || busy} /></label>
    <button disabled={disabled || busy || (!file && !text.trim())} onClick={() => void read()}>Read this bill</button>
    <div aria-live="polite" role="status"><p>{busy ? "Reading your bill..." : notice}</p>{bill && <>
      {bill.ai && <span className="chip neutral">{bill.ai.enabled ? "AI assist is on" : bill.ai.note}</span>}
      <table className="bill-fields"><caption>What I read from your bill (check it against the paper)</caption><tbody>{[["Supplier", "supplier_name"], ["GSTIN - supplier’s GST identification number", "supplier_gstin"], ["Invoice no - bill number", "invoice_no"], ["Date", "invoice_date"], ["Taxable value - amount before GST", "taxable"], ["GST rate - tax percentage", "rate"], ["Total", "total_amount"]].map(([label, key]) => <tr key={key}><th scope="row">{label}</th><td>{["taxable", "total_amount"].includes(key) && /^\d+(?:\.\d{1,2})?$/.test((bill.extracted[key] || "").replace(/,/g, "")) ? rupees(paise(bill.extracted[key]!.replace(/,/g, ""))) : bill.extracted[key] || "Not read"}</td></tr>)}</tbody></table>
      <ul>{bill.questions.map((q, i) => <li key={i}>{q}</li>)}{bill.flags.map((f, i) => <li key={`flag-${i}`}>{flagMessage(f)}</li>)}</ul><p>{bill.plain}</p>
      {bill.draft && <><table><caption>Recorded lines - the categories and both matching sides</caption><thead><tr><th>Ledger (category)</th><th>Side</th><th>Amount</th></tr></thead><tbody>{bill.draft.lines.map((l, i) => <tr key={i}><td>{l.ledger}</td><td>{l.side === "Dr" ? "Debit - money goes into" : "Credit - money comes out of"}</td><td>{rupees(paise(l.amount))}</td></tr>)}</tbody></table><button disabled={disabled || busy} onClick={() => { try { onAdd(bill.draft!); setBill(undefined); } catch (e) { setNotice((e as Error).message); } }}>Add to my batch</button></>}
    </>}</div></div>;
}
