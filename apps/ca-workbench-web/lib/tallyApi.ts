export interface Line { ledger: string; amount: string; side: "Dr" | "Cr" }
export interface Draft {
  vtype: "Sales" | "Purchase" | "Payment" | "Receipt" | "Journal" | "Contra";
  date: string; party: string; narration: string; flags: string[]; lines: Line[];
  number?: string; reference?: string; reference_date?: string | null; party_gstin?: string;
  place_of_supply?: string; confidence?: string; source?: string; plain?: string;
}
export interface Ledger { name: string; parent: string; meaning?: string; duty_head?: string; gstin?: string }
export interface Pack { ledgers: Ledger[]; xml: string }
export interface Entry { draft: Draft | null; questions: string[]; flags: string[]; interpretation: string; plain?: string; xml_preview?: string }
export interface Statement { drafts: Draft[]; errors: string[]; skipped: number; summary: Record<string, string | number> }
export type BatchStatus = "PENDING_APPROVAL" | "APPROVED" | "POSTED" | "FAILED" | "REJECTED";
export interface BatchSummary {
  count: number; total?: string;
  items: { name?: string; parent?: string; vtype?: string; date?: string; party?: string; amount?: string; flags?: string[] }[];
}
export interface Staged { batch_id: string; payload_sha256: string; status: BatchStatus; summary: BatchSummary }
export interface Batch { batch_id: string; sha256: string; status: BatchStatus; company: string; kind: string; summary: BatchSummary; ack?: { created?: number; errors?: string[] }; created_at?: string }
export interface Bridge { bridge_id: string; company: string; host: string | null; paired: boolean; revoked: boolean; last_seen: string | null }
export interface Setup { company: string; business_type: "trader" | "service" | "manufacturer"; state_code: string }
export interface BatchInput { company: string; drafts: Draft[] }

export async function call<T>(path: string, options: { method?: string; body?: unknown; token?: string; headers?: Record<string, string>; signal?: AbortSignal } = {}): Promise<T> {
  const headers: Record<string, string> = { ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  let response: Response;
  try {
    response = await fetch(`/api/v1/${path}`, { method: options.method ?? "GET", headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: options.signal });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new Error("Cannot reach TaxSetu. Check your connection and try again.");
  }
  const text = await response.text();
  let data: unknown;
  try { data = text ? JSON.parse(text) : undefined; } catch { data = undefined; }
  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : undefined;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(d => typeof d?.msg === "string" ? d.msg : "Invalid request").join("; ") : `TaxSetu request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }
  if (text && data === undefined) throw new Error("TaxSetu returned an unreadable response. Please try again.");
  return data as T;
}

const post = <T>(path: string, body: unknown, token?: string) => call<T>(path, { method: "POST", body, token });
export const tallyApi = {
  starterPack: (business_type: Setup["business_type"], state_code: string) => call<Pack>(`tally/sandbox/starter-pack?${new URLSearchParams({ business_type, state_code })}`),
  entry: (text: string, state_code: string, token?: string) => post<Entry>(`tally/${token ? "" : "sandbox/"}entry`, { text, state_code }, token),
  statement: (csv: string, state_code: string, token?: string) => post<Statement>(`tally/${token ? "" : "sandbox/"}bank-statement`, { csv, state_code }, token),
  voucherXml: (body: BatchInput) => post<{ xml: string; count: number }>("tally/sandbox/voucher-xml", body),
  devToken: (tenant_id: string, adminKey: string) => call<{ token: string; expires_in_s: number }>("auth/dev-token", { method: "POST", body: { tenant_id, role: "OWNER" }, headers: { "X-Admin-Key": adminKey } }),
  stage: (body: BatchInput, token: string) => post<Staged>("tally/batches", body, token),
  batches: (token: string) => call<{ batches: Batch[] }>("tally/batches", { token }),
  batch: (id: string, token: string, signal?: AbortSignal) => call<Batch>(`tally/batches/${encodeURIComponent(id)}`, { token, signal }),
  approve: (id: string, payload_sha256: string, token: string) => post<{ status: BatchStatus }>(`tally/batches/${encodeURIComponent(id)}/approve`, { payload_sha256 }, token),
  reject: (id: string, token: string) => post<{ status: BatchStatus }>(`tally/batches/${encodeURIComponent(id)}/reject`, undefined, token),
  setup: (body: Setup, token: string) => post<Staged | { nothing_to_do: true }>("tally/setup", body, token),
  alias: (party: string, ledger: string, token: string) => post<{ learned: Record<string, string> }>("tally/aliases", { party, ledger }, token),
  ledgers: (token: string) => call<{ ledgers: Ledger[] }>("tally/ledgers", { token }),
  createBridge: (company: string, token: string) => post<{ bridge_id: string; pairing_code: string; expires_in_s: number }>("tally/bridges", { company }, token),
  bridges: (token: string) => call<{ bridges: Bridge[] }>("tally/bridges", { token }),
  revokeBridge: (id: string, token: string) => call<{ revoked: boolean }>(`tally/bridges/${encodeURIComponent(id)}`, { method: "DELETE", token }),
};
