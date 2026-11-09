import { call, type Staged } from "./tallyApi.ts";
export type EntityType = "business" | "individual" | "nonprofit";
export interface NotebookEntry { date: string; description: string; receipt?: string; payment?: string; mode?: "cash" | "bank"; party?: string; hint?: string }
export type Figures = Record<string, string | Record<string, string>>;
export interface Book { name: string; entity_type: EntityType; period_start: string; period_end: string; opening: Figures; closing: Figures; entries: NotebookEntry[] }
export interface SavedBook extends Omit<Book, "entries"> { book_id: string; status: "OPEN" | "CLOSED"; rolled_from?: string }
export interface SavedEntry extends NotebookEntry { entry_id: string; status: "ACTIVE" | "VOID"; void_reason?: string | null }
export interface JournalItem { date: string; source: string; narration: string; flags?: string[]; lines: { ledger: string; amount: string; side: "Dr" | "Cr" }[] }
export type StatementValue = string | boolean | { [key: string]: StatementValue };
export type Statements = Record<string, Record<string, StatementValue>>;
export interface Conversion { statements: Statements; journal: JournalItem[]; ledgers: Record<string, { debit?: string; credit?: string; dr?: string; cr?: string; balance: string; side: string }>; trial_balance: { balanced: boolean; rows: { ledger: string; debit: string; credit: string }[]; total_debit?: string; total_credit?: string }; crosscheck: Record<string, string | boolean>; counts: Record<string, number>; questions: string[]; warnings: string[]; errors: string[] }
export interface Example { id: string; title: string; description: string; entity_type: EntityType; entries: number }
const idPath = (id: string) => `books/${encodeURIComponent(id)}`;
const post = <T>(path: string, body: unknown, token?: string) => call<T>(path, { method: "POST", body, token });
export const booksApi = {
  examples: () => call<{ examples: Example[] }>("books/sandbox/examples"),
  example: (id: string) => call<{ book: Book }>(`books/sandbox/examples/${encodeURIComponent(id)}`),
  parseCsv: (csv: string) => post<{ entries: NotebookEntry[]; errors: string[] }>("books/sandbox/parse-csv", { csv }),
  convert: (book: Book) => post<Conversion>("books/sandbox/convert", { book }),
  list: (token: string) => call<{ books: SavedBook[] }>("books", { token }),
  get: (id: string, token: string) => call<SavedBook>(idPath(id), { token }),
  create: (book: Omit<Book, "entries">, token: string) => post<SavedBook>("books", book, token),
  entries: (id: string, token: string, includeVoid = false) => call<{ entries: SavedEntry[] }>(`${idPath(id)}/entries?include_void=${includeVoid}`, { token }),
  add: (id: string, entries: NotebookEntry[], csv: string, token: string) => post<{ added: number; errors: string[]; entries: SavedEntry[] }>(`${idPath(id)}/entries`, { entries, csv }, token),
  void: (id: string, eid: string, reason: string, token: string) => post<{ voided: boolean }>(`${idPath(id)}/entries/${encodeURIComponent(eid)}/void`, { reason }, token),
  setup: (id: string, opening: Figures, closing: Figures, token: string) => call<SavedBook>(`${idPath(id)}/setup`, { method: "PUT", body: { opening, closing }, token }),
  report: (id: string, token: string) => call<{ status: string; report: Conversion }>(`${idPath(id)}/report`, { token }),
  close: (id: string, accept_review: boolean, token: string) => post<{ status: string; report: Conversion }>(`${idPath(id)}/close`, { accept_review }, token),
  rollover: (id: string, token: string) => post<SavedBook>(`${idPath(id)}/rollover`, {}, token),
  tally: (id: string, company: string, accept_review: boolean, token: string) => post<{ staged: (Staged & { what: string })[]; note: string }>(`${idPath(id)}/tally`, { company, accept_review }, token),
};
