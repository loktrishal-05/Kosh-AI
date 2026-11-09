import test from "node:test";
import assert from "node:assert/strict";
import { currentSession, endSession, isLive, saveSession, tokenExpiry } from "./session.ts";

const jwt = (claims: object) => `h.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.s`;
const withStorage = (fn: (items: Map<string, string>) => void) => {
  const items = new Map<string, string>();
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, value: { getItem: (k: string) => items.get(k) ?? null, setItem: (k: string, v: string) => items.set(k, v), removeItem: (k: string) => items.delete(k) } });
  try { fn(items); } finally { if (descriptor) Object.defineProperty(globalThis, "sessionStorage", descriptor); else Reflect.deleteProperty(globalThis, "sessionStorage"); }
};
const user = { name: "Demo Admin", role: "OWNER", demo: true };

test("the token's own expiry is read, and anything unreadable counts as expired", () => {
  assert.equal(tokenExpiry(jwt({ exp: 2000 })), 2_000_000);
  for (const bad of ["", "abc", "a.b.c", "a.!!!.c", jwt({ nope: 1 }), jwt({ exp: "soon" })]) assert.equal(tokenExpiry(bad), 0, bad);
  assert.equal(isLive(jwt({ exp: 2000 }), 1_999_000), true);
  assert.equal(isLive(jwt({ exp: 2000 }), 2_000_001), false);
  assert.equal(isLive("", 0), false);
});

test("signing in stores the one token every page reads, and signing out removes everything", () => withStorage(items => {
  const token = jwt({ exp: 4_000_000_000 });
  assert.equal(currentSession(), null);
  saveSession(token, user);
  assert.deepEqual(currentSession(), { token, user });
  assert.equal(items.get("taxsetu-tally-token"), token);                  // the key the Tally and Books pages already use
  endSession();
  assert.equal(currentSession(), null);
  assert.equal(items.size, 0);
}));

test("an expired or admin-key token is handled: expired means signed out, a token without a user still counts as signed in", () => withStorage(items => {
  saveSession(jwt({ exp: 10 }), user);
  assert.equal(currentSession(Date.now()), null);
  items.clear();
  items.set("taxsetu-tally-token", jwt({ exp: 4_000_000_000 }));          // the older admin-key sign-in on the Tally page
  assert.deepEqual(currentSession()?.user, null);
  assert.ok(currentSession());
  items.set("taxsetu-session-user", "{not json");
  assert.ok(currentSession() && currentSession()!.user === null);
}));

test("blocked storage never throws", () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, get() { throw new Error("Storage blocked"); } });
  try { saveSession("x", user); assert.equal(currentSession(), null); endSession(); }
  finally { if (descriptor) Object.defineProperty(globalThis, "sessionStorage", descriptor); else Reflect.deleteProperty(globalThis, "sessionStorage"); }
});
