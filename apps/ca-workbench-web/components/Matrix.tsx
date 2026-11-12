"use client";
import { useState } from "react";
import Link from "next/link";
import type { Client } from "../lib/mock";
import { byPriority, priorityScore } from "../lib/priority";
import { formatMoney } from "../lib/money";
import { WORKBENCH } from "../lib/workbenchText";
import { statusLabels } from "./StatusChip";
import { BarChart, HorizontalBarChart } from "./app/charts";
import { CountUp } from "./app/CountUp";
import { ViewState } from "./app/ViewState";

const batches = [
  { id: "all", label: "All", match: (_: Client) => true },
  { id: "ready", label: "Ready to File", match: (c: Client) => c.readyToFile },
  { id: "vendor", label: "Pending Vendor 2B Responses", match: (c: Client) => c.pendingVendor2b > 0 },
  { id: "adjustment", label: "Rule 37 / RCM Adjustments Needed", match: (c: Client) => c.rule37Adjustments + c.rcmAdjustments > 0 },
  { id: "cash", label: "Cash Shortfall Alerts", match: (c: Client) => c.cashShortfall },
];
type SortKey = "priority" | "businessName" | "exceptions" | "deadline" | "netGstPayablePaise";

export function Matrix({ initialClients }: { initialClients: Client[] }) {
  return <ViewState><MatrixContent initialClients={initialClients} /></ViewState>;
}
function MatrixContent({ initialClients }: { initialClients: Client[] }) {
  const t = WORKBENCH.en;
  const [clients, setClients] = useState(initialClients);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: "priority", ascending: false });
  const [message, setMessage] = useState("");
  const searched = clients.filter(c => `${c.businessName} ${c.gstin} ${c.id}`.toLowerCase().includes(search.trim().toLowerCase()));
  const visible = searched.filter(batches.find(b => b.id === filter)!.match).sort((a, b) => {
    const first = sort.key === "priority" ? priorityScore(a) : a[sort.key];
    const second = sort.key === "priority" ? priorityScore(b) : b[sort.key];
    const comparison = typeof first === "number" && typeof second === "number" ? first - second : String(first).localeCompare(String(second));
    return (sort.ascending ? comparison : -comparison) || byPriority(a, b);
  });
  const eligible = visible.filter(c => c.readyToFile && !c.otpRequested);
  function requestOtp() {
    const ids = new Set(eligible.map(c => c.id));
    setClients(previous => previous.map(c => ids.has(c.id) ? { ...c, otpRequested: true } : c));
    setMessage(`OTP request queued for ${ids.size} clients. Clients approve and file themselves.`);
  }
  function sortColumn(key: SortKey, label: string) {
    return <th scope="col" aria-sort={sort.key === key ? sort.ascending ? "ascending" : "descending" : "none"}><button className="sort" onClick={() => setSort({ key, ascending: sort.key === key ? !sort.ascending : key === "businessName" || key === "deadline" })}>{label} <span aria-hidden="true">{sort.key === key ? sort.ascending ? "↑" : "↓" : "↕"}</span></button></th>;
  }
  const ready = clients.filter(c => c.readyToFile).length;
  const invoices = visible.flatMap(c => c.invoices);
  const statusData = (Object.keys(statusLabels) as (keyof typeof statusLabels)[]).map(status => ({ label: statusLabels[status], value: invoices.filter(i => i.status === status).length, highlight: status === "MISSING_2B" }));
  const priorityData = [0, 50, 100, 150].map((min, i) => ({ label: `${i === 3 ? "150+" : `${min}–${min + 49}`} ${t.priorityPoints}`, value: visible.filter(c => priorityScore(c) >= min && (i === 3 || priorityScore(c) < min + 50)).length, highlight: i === 3 }));
  if (!clients.length) return <section className="panel empty"><h1>{t.emptyClients}</h1><Link className="button-link primary" href="/books">{t.openBooks}</Link></section>;
  return <>
    <section className="page-heading"><div><p className="eyebrow">COMPLIANCE OPERATIONS / {clients.length} CLIENTS</p><h1>Exception Matrix<span className="title-dot">.</span></h1><p className="muted">One workspace. Every client. The next priority, already surfaced.</p></div><div><label htmlFor="period">Reporting period · demo</label><select id="period" defaultValue="October 2026"><option>October 2026</option></select></div></section>
    <section className="summary" aria-label="Portfolio summary">{([["Clients", clients.length], ["Ready to file", ready], ["With exceptions", clients.length - ready], ["Total exceptions", clients.reduce((n, c) => n + c.exceptions, 0)]] as const).map(([label, value], i) => <div className={`tile tile-${i}`} key={label}><span>{label}</span><strong><CountUp value={value} /></strong><small>{i === 1 ? "Client OTP required" : i === 3 ? "Across the portfolio" : "October workspace"}</small></div>)}</section>
    {visible.length > 0 && <><div className="charts-grid"><BarChart title={t.invoiceStatuses} unit={t.invoiceCount} data={statusData} /><HorizontalBarChart title={t.priorities} unit={t.clients} data={priorityData} /></div><p className="footnote">{t.priorityNote}</p></>}
    <section className="panel" aria-labelledby="queue-title"><div className="panel-heading"><div><p className="eyebrow">YOUR WORK QUEUE</p><h2 id="queue-title">Clients needing attention</h2></div><span className="chip neutral">As of 18 Nov 2026 · demo clock</span></div>
      <div className="filters" aria-label="Client batch filters">{batches.map(batch => <button key={batch.id} aria-pressed={filter === batch.id} onClick={() => setFilter(batch.id)}>{batch.label} <span>{searched.filter(batch.match).length}</span></button>)}</div>
      <div className="toolbar"><div className="search"><label htmlFor="search">Search clients</label><input id="search" type="search" placeholder="Business name, GSTIN or client ID" value={search} onChange={e => setSearch(e.target.value)} /></div><p className="muted">{visible.length} of {clients.length} clients</p>{filter === "ready" && <button className="primary" disabled={!eligible.length} onClick={requestOtp}>Request client OTP ({eligible.length})</button>}</div>
      <p className="live-status" role="status" aria-live="polite">{message}</p>
      <div className="table-region" role="region" aria-label="Client exception matrix, scroll horizontally for all columns" tabIndex={0}><table><caption className="sr-only">Client priority queue. Follow the business name to review invoices. Default priority combines exceptions and deadline proximity.</caption><thead><tr>{sortColumn("businessName", "Client / GSTIN")}{sortColumn("priority", "Priority")}<th scope="col">Vendor 2B</th><th scope="col">Rule 37 / RCM</th><th scope="col">Cash coverage</th>{sortColumn("exceptions", "Exceptions")}{sortColumn("netGstPayablePaise", "Net GST payable")}{sortColumn("deadline", "Due date")}<th scope="col">Readiness</th></tr></thead><tbody>{visible.map(c => <tr key={c.id}>
        <th scope="row"><Link className="client-link" href={`/clients/${c.id}`}>{c.businessName}<span aria-hidden="true"> ↗</span></Link><small className="mono">{c.gstin}</small><small>{c.constitution} · {c.filing}</small></th>
        <td><span className={`chip ${c.exceptions ? "warning" : "success"}`}>{c.exceptions ? `! ${priorityScore(c)}` : "✓ Clear"}</span></td><td>{c.pendingVendor2b || "—"}</td><td>{c.rule37Adjustments} / {c.rcmAdjustments}</td><td>{c.cashShortfall ? "! Shortfall · " : "✓ "}{c.cashRatioPct}%</td><td><strong>{c.exceptions}</strong></td><td className="money">{formatMoney(c.netGstPayablePaise)}</td><td>{c.deadline}<small>{c.filing}</small></td><td>{c.otpRequested ? <span className="chip neutral">◷ OTP queued</span> : c.readyToFile ? <span className="chip success">✓ Ready</span> : <span className="muted">! Review needed</span>}</td>
      </tr>)}</tbody></table>{!visible.length && <div className="empty" role="status"><h3>No clients match</h3><p>Try another batch or search term.</p><button type="button" onClick={() => { setFilter("all"); setSearch(""); }}>{t.resetFilters}</button></div>}</div>
    </section><p className="footnote">Priority = exceptions × 10 + deadline proximity (up to 30 points). QRMP records show October activity within the Oct–Dec quarter; the due date is illustrative.</p>
  </>;
}
