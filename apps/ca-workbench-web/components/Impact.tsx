"use client";
import { useState } from "react";
import { impact, STATEMENT } from "../lib/impact";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

/** What "half the sorting arrives done" is worth, using only the figures in the problem statement. Move the sliders to test other assumptions. */
export function Impact() {
  const [hours, setHours] = useState(18), [fee, setFee] = useState(2000), [filings, setFilings] = useState(12), [share, setShare] = useState(50);
  const r = impact({ hoursPerMonth: hours, feePerFiling: fee, filingsPerYear: filings, shareDone: share / 100 });
  return <section className="impact">
    <p className="eyebrow">IMPACT MODEL</p>
    <h1>What does it save?</h1>
    <p className="muted">An illustration from the figures in the problem statement ({STATEMENT.hoursPerMonth[0]}-{STATEMENT.hoursPerMonth[1]} hours a month, {inr.format(STATEMENT.feePerFiling[0])}-{inr.format(STATEMENT.feePerFiling[1])} per filing). It is a model, not a measured result: the real share of work done must be measured in a pilot.</p>
    <div className="impact-inputs">
      <label>Owner hours a month on paperwork: {hours}<input type="range" min="5" max="30" value={hours} onChange={e => setHours(+e.target.value)} /></label>
      <label>Accountant fee per filing: {inr.format(fee)}<input type="range" min="500" max="5000" step="100" value={fee} onChange={e => setFee(+e.target.value)} /></label>
      <label>Filings a year: {filings}<input type="range" min="4" max="24" value={filings} onChange={e => setFilings(+e.target.value)} /></label>
      <label>Share of the sorting that arrives done: {share}%<input type="range" min="0" max="90" step="5" value={share} onChange={e => setShare(+e.target.value)} /></label>
    </div>
    <div className="summary">
      <div className="tile tile-1"><span>Owner hours saved a month</span><strong>{r.hoursSavedMonth}</strong><small>{r.hoursSavedYear} hours a year</small></div>
      <div className="tile"><span>Accountant effort saved a year</span><strong className="amount">{inr.format(r.feeAtStakeYear)}</strong><small>of fees spent on sorting, not advice</small></div>
      <div className="tile"><span>Clients one accountant can carry</span><strong>{r.accountantCapacity}×</strong><small>at the same working hours</small></div>
    </div>
  </section>;
}
