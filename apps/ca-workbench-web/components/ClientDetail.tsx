"use client";
import { useState } from "react";
import Link from "next/link";
import type { Client } from "../lib/mock";
import { formatMoney } from "../lib/money";
import { buildTallyXml } from "../lib/tally";
import { DiffViewer } from "./DiffViewer";
import { statusLabels } from "./StatusChip";

export function ClientDetail({ client }: { client: Client }) {
  const [message, setMessage] = useState("");
  function exportXml() {
    try {
      const url = URL.createObjectURL(new Blob([buildTallyXml(client)], { type: "application/xml;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url; link.download = `${client.id}-purchases.xml`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage("Tally XML download prepared. Validate ledger mapping in a test company before import.");
    } catch { setMessage("XML export failed. No file was downloaded. Please try again."); }
  }
  const issues = client.invoices.flatMap(invoice => [
    ...(invoice.status !== "EXACT" ? [`${statusLabels[invoice.status]}: compare register and 2B values.`] : []),
    ...(invoice.rule37 ? ["Rule 37 adjustment: review unpaid vendor balance."] : []),
    ...(invoice.rcm ? ["RCM adjustment: review reverse-charge treatment."] : []),
    ...(invoice.cashShortfall ? [`Cash shortfall alert: available cash covers ${client.cashRatioPct}% of the demo liability.`] : []),
  ].map(text => ({ id: `${invoice.id}-${text}`, invoiceNumber: invoice.register.invoiceNumber, text })));
  return <><Link className="back" href="/">← Exception Matrix</Link><section className="page-heading"><div><p className="eyebrow">CLIENT RECORD / {client.id}</p><h1>{client.businessName}</h1><p className="muted mono">{client.gstin} · {client.constitution}</p></div><button className="primary" onClick={exportXml}>Export Tally XML ↓</button></section>
    <p className="live-status" role="status" aria-live="polite">{message}</p>
    <section className="summary" aria-label="Client summary"><div className="tile"><span>Net GST payable</span><strong className="amount">{formatMoney(client.netGstPayablePaise)}</strong><small>Illustrative liability</small></div><div className="tile"><span>Reporting period</span><strong className="amount">{client.period}</strong><small>{client.filing} · Due {client.deadline}</small></div><div className="tile"><span>Open exceptions</span><strong>{client.exceptions}</strong><small>{client.pendingVendor2b} missing vendor 2B records</small></div><div className="tile"><span>Readiness</span><strong className="amount">{client.readyToFile ? "✓ Ready" : "! Review needed"}</strong><small>Clients approve and file themselves</small></div></section>
    <DiffViewer invoices={client.invoices} />
    <section className="panel exceptions" aria-labelledby="exceptions-title"><p className="eyebrow">FOLLOW-UP</p><h2 id="exceptions-title">Exceptions ({issues.length})</h2>{issues.length ? <ul>{issues.map(issue => <li key={issue.id}><span className="mono">{issue.invoiceNumber}</span><p>{issue.text}</p></li>)}</ul> : <p>✓ No open exceptions. Client approval is still required.</p>}</section>
    <p className="footnote">Tally XML is generated locally from the purchase register. Its voucher shape has not been verified against live TallyPrime. Review ledger names and import into a test company first.</p>
  </>;
}
