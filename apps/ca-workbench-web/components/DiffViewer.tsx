"use client";
import { useState } from "react";
import type { Invoice, InvoiceStatus } from "../lib/mock";
import { formatMoney } from "../lib/money";
import { StatusChip, statusLabels } from "./StatusChip";

export function DiffViewer({ invoices }: { invoices: Invoice[] }) {
  const [status, setStatus] = useState<InvoiceStatus | "ALL">("ALL");
  const visible = invoices.filter(i => status === "ALL" || i.status === status);
  return <section className="panel" aria-labelledby="diff-title"><div className="panel-heading"><div><p className="eyebrow">RECONCILIATION</p><h2 id="diff-title">Purchase register ↔ GSTR-2B</h2></div><span className="muted">{visible.length} / {invoices.length} invoices</span></div>
    <div className="filters" aria-label="Invoice status filters"><button aria-pressed={status === "ALL"} onClick={() => setStatus("ALL")}>All ({invoices.length})</button>{(Object.keys(statusLabels) as InvoiceStatus[]).map(s => <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)}>{statusLabels[s]} ({invoices.filter(i => i.status === s).length})</button>)}</div>
    <p className="sr-only" role="status" aria-live="polite">Showing {visible.length} invoices</p>
    <div className="table-region" role="region" aria-label="Invoice comparison, scroll horizontally for both records" tabIndex={0}><table className="diff-table"><caption>! Different = a value needs review. − No record = vendor invoice absent from GSTR-2B.</caption><thead><tr><th rowSpan={2} scope="col">Vendor / status</th><th colSpan={3} scope="colgroup">Our purchase register</th><th colSpan={3} scope="colgroup">GSTR-2B</th></tr><tr>{["Our", "2B"].flatMap(group => ["Invoice number", "Taxable value", "Tax"].map(label => <th key={group + label} scope="col">{label}</th>))}</tr></thead><tbody>{visible.map(invoice => <tr key={invoice.id}><th scope="row">{invoice.vendor}<small><StatusChip status={invoice.status} /></small></th>{([invoice.register, invoice.gstr2b] as const).map((record, side) => (["invoiceNumber", "taxablePaise", "taxPaise"] as const).map(field => {
      const differs = invoice.register[field] !== invoice.gstr2b?.[field];
      return <td key={`${side}-${field}`} className={differs ? "different" : undefined}>{record ? field === "invoiceNumber" ? record[field] : formatMoney(record[field]) : "—"}{differs && <small>{record ? "! Different" : "− No record"}</small>}</td>;
    }))}</tr>)}</tbody></table>{!visible.length && <p className="empty">No invoices with this status.</p>}</div>
  </section>;
}
