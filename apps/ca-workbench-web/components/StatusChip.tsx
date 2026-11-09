import type { InvoiceStatus } from "../lib/mock";
export const statusLabels: Record<InvoiceStatus, string> = { EXACT: "✓ Exact match", FUZZY: "≈ Invoice typo", MISMATCH: "! Tax mismatch", MISSING_2B: "− Missing in 2B" };
export function StatusChip({ status }: { status: InvoiceStatus }) { return <span className={`chip ${status === "EXACT" ? "success" : "warning"}`}>{statusLabels[status]}</span>; }
