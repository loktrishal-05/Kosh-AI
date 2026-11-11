import test from "node:test";
import assert from "node:assert/strict";
import { ownerCards, LANGS } from "./ownerText.ts";
import { clients } from "./mock.ts";

const today = new Date("2026-11-11T00:00:00");
test("every language gives the same cards for the same client, and the last card says a human files", () => {
  const c = clients.find(x => x.pendingVendor2b > 0 && x.cashShortfall)!;
  const shapes = LANGS.map(l => ownerCards(c, l.code, today).map(k => k.id).join());
  assert.equal(new Set(shapes).size, 1);
  assert.match(shapes[0], /due,missing.*cash.*pay,safe$/);
  assert.match(ownerCards(c, "en", today)[0].text, /due in 9 days/);
});
test("a clean client is told there is nothing to do", () => {
  const c = clients.find(x => x.readyToFile)!;
  assert.ok(ownerCards(c, "hi", today).some(k => k.id === "ok"));
});
test("no card is empty, and a past-due date reads as 0 days, never negative", () => {
  for (const c of clients.slice(0, 20)) for (const l of LANGS) for (const k of ownerCards(c, l.code, new Date("2027-06-01T00:00:00"))) assert.ok(k.text.length > 10 && !k.text.includes("-"));
});
