import type { Draft } from "./tallyApi.ts";

const messages: Record<string, string> = {
  AI_SUGGESTED: "AI suggests this ledger. Please check it.",
  TOTAL_MISMATCH: "The printed total does not match the amount plus GST. Check the paper bill.",
  TOTAL_UNREADABLE: "We could not read the printed total. Check it against the paper bill.",
  INVOICE_NO_MISSING: "The bill number is missing. Look for it on the paper bill.",
  GSTIN_INVALID: "The supplier's GST identification number looks invalid. Check it with the supplier.",
  GSTIN_MISSING: "The supplier's GST identification number is missing. Ask the supplier for it.",
  ITC_BLOCKED_17_5: "GST paid on this purchase may not be claimable under section 17(5). Ask your accountant before claiming it.",
  GST_ASSUMED_INTRASTATE: "We assumed the supplier is in your state when splitting GST. Check the supplier's state.",
  NEEDS_REVIEW: "Please check this entry before adding it to your books.",
  SUSPICIOUS_TEXT: "This text contains unusual instructions. Check the transaction details before continuing.",
};
export function flagMessage(flag: string): string {
  if (flag.startsWith("AI_SUGGESTED:")) return `AI suggests this ledger: ${flag.slice(13).replace(/\.$/, "")}. Please check it.`;
  return flag.startsWith("NEW_LEDGER:") ? `First time we see ${flag.slice(11)}; we will create it in Tally` : messages[flag] ?? flag;
}
export function setLedger(draft: Draft, fromLedger: string, toLedger: string): Draft {
  return { ...draft, lines: draft.lines.map(line => line.ledger === fromLedger ? { ...line, ledger: toLedger } : { ...line }) };
}
export function bankNeedsCheck(draft: Draft): boolean {
  return draft.lines.some(line => line.ledger === "Suspense A/c") || draft.flags.some(flag => flag === "NEEDS_REVIEW" || flag.startsWith("AI_SUGGESTED"));
}
export function paise(amount: string): bigint {
  if (!/^\d+(?:\.\d{1,2})?$/.test(amount)) throw new Error("Amount must be a non-negative rupee string with at most two decimal places");
  const [whole, fraction = ""] = amount.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}
export function rupees(value: bigint): string {
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}₹${new Intl.NumberFormat("en-IN").format(absolute / 100n)}.${String(absolute % 100n).padStart(2, "0")}`;
}
export function batchTotals(drafts: readonly Draft[]) {
  let debit = 0n, credit = 0n, total = 0n, moneyIn = 0n, moneyOut = 0n;
  for (const draft of drafts) {
    let dr = 0n, cr = 0n;
    for (const line of draft.lines) {
      const amount = paise(line.amount);
      if (line.side === "Dr") dr += amount; else cr += amount;
      if (line.ledger === "Bank Account") {
        if (line.side === "Dr") moneyIn += amount; else moneyOut += amount;
      }
    }
    debit += dr; credit += cr; total += dr > cr ? dr : cr;
  }
  return { debit, credit, total, moneyIn, moneyOut };
}
export const sampleBankCsv = `Date,Narration,Debit,Credit
2026-10-01,RENT SHARMA,25000.00,
2026-10-02,SALARY OCTOBER,18000.00,
2026-10-03,UPI RAO TRADERS RECEIPT,,40000.00
2026-10-04,BANK CHARGES,118.00,
2026-10-05,ATM WITHDRAWAL,5000.00,
2026-10-06,UPI MYSTERY PAYEE,750.00,
2026-10-07,RENT WAREHOUSE,8000.00,
2026-10-08,SALARY ASSISTANT,12000.00,
2026-10-09,UPI CUSTOMER RECEIPT,,15000.00
2026-10-10,BANK CHARGES,59.00,`;

const tokenKey = "taxsetu-tally-token";
export function getToken(): string { try { return sessionStorage.getItem(tokenKey) ?? ""; } catch { return ""; } }
export function setToken(token: string): void { try { sessionStorage.setItem(tokenKey, token); } catch { /* Storage may be blocked; this tab can still sign in. */ } }
export function clearToken(): void { try { sessionStorage.removeItem(tokenKey); } catch { /* Storage may be unavailable. */ } }
