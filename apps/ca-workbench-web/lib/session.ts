import { clearToken, getToken, setToken } from "./tallyFlow.ts";
export interface SessionUser { name: string; role: string; demo: boolean }
const userKey = "taxsetu-session-user";
/** The token's own expiry (ms since epoch), 0 when it cannot be read. The server is the real judge; this only avoids showing pages with a dead token. */
export function tokenExpiry(token: string): number {
  try { const part = token.split(".")[1] ?? ""; return (Number(JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/"))).exp) || 0) * 1000; } catch { return 0; }
}
export function isLive(token: string, now = Date.now()): boolean { return !!token && tokenExpiry(token) > now; }
/** One sign-in for the whole workbench: the same token the Tally and Books pages already read, plus who is signed in. */
export function saveSession(token: string, user: SessionUser): void {
  setToken(token);
  try { sessionStorage.setItem(userKey, JSON.stringify(user)); } catch { /* storage blocked: this tab still holds the token in memory of the page that set it */ }
}
export function currentSession(now = Date.now()): { token: string; user: SessionUser | null } | null {
  const token = getToken();
  if (!isLive(token, now)) return null;
  try { const user = JSON.parse(sessionStorage.getItem(userKey) ?? "null"); return { token, user: user && typeof user.name === "string" ? user : null }; } catch { return { token, user: null }; }
}
export function endSession(): void {
  clearToken();
  try { sessionStorage.removeItem(userKey); } catch { /* storage unavailable */ }
}
