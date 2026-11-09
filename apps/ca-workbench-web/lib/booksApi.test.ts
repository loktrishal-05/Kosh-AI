import test from "node:test";
import assert from "node:assert/strict";
import { booksApi } from "./booksApi.ts";
import { ApiError, tallyApi } from "./tallyApi.ts";
test("books API uses exact routes, methods and payloads, and authenticates only connected calls", async () => {
  const original = globalThis.fetch;
  const requests: { path: string; init?: RequestInit }[] = [];
  globalThis.fetch = async (input, init) => { requests.push({ path: String(input), init }); return new Response("{}"); };
  const book = { name: "Shop", entity_type: "business" as const, period_start: "2026-04-01", period_end: "2027-03-31", opening: {}, closing: {}, entries: [] };
  try {
    await booksApi.examples(); await booksApi.example("a/b"); await booksApi.parseCsv("csv"); await booksApi.convert(book);
    await booksApi.list("t"); await booksApi.get("a/b", "t"); await booksApi.create(book, "t"); await booksApi.entries("a/b", "t", true);
    await booksApi.add("a/b", [], "csv", "t"); await booksApi.void("a/b", "e/f", "duplicate", "t"); await booksApi.setup("a/b", { cash: "100.01" }, {}, "t");
    await booksApi.report("a/b", "t"); await booksApi.close("a/b", true, "t"); await booksApi.rollover("a/b", "t"); await booksApi.tally("a/b", "Shop", true, "t");
    assert.deepEqual(requests.map(r => r.path), ["/api/v1/books/sandbox/examples", "/api/v1/books/sandbox/examples/a%2Fb", "/api/v1/books/sandbox/parse-csv", "/api/v1/books/sandbox/convert", "/api/v1/books", "/api/v1/books/a%2Fb", "/api/v1/books", "/api/v1/books/a%2Fb/entries?include_void=true", "/api/v1/books/a%2Fb/entries", "/api/v1/books/a%2Fb/entries/e%2Ff/void", "/api/v1/books/a%2Fb/setup", "/api/v1/books/a%2Fb/report", "/api/v1/books/a%2Fb/close", "/api/v1/books/a%2Fb/rollover", "/api/v1/books/a%2Fb/tally"]);
    for (const [i, r] of requests.entries()) assert.equal(new Headers(r.init?.headers).get("Authorization"), i < 4 ? null : "Bearer t");
    assert.equal(requests[10].init?.method, "PUT");
    assert.deepEqual(JSON.parse(String(requests[3].init?.body)), { book });
    assert.deepEqual(JSON.parse(String(requests[12].init?.body)), { accept_review: true });
    assert.deepEqual(JSON.parse(String(requests[9].init?.body)), { reason: "duplicate" });
  } finally { globalThis.fetch = original; }
});
test("bill reader sends exact fields and preserves AI-off and validation details with status", async () => {
  const original = globalThis.fetch;
  const body = { text: "bill", image_base64: "YWJj", media_type: "image/png", state_code: "29" };
  try {
    globalThis.fetch = async (input, init) => { assert.equal(input, "/api/v1/tally/invoice"); assert.equal(new Headers(init?.headers).get("Authorization"), "Bearer t"); assert.deepEqual(JSON.parse(String(init?.body)), body); return new Response('{"draft":null,"ai":{"enabled":false,"note":"AI is off"}}'); };
    assert.equal((await tallyApi.readBill(body, "t")).ai?.enabled, false);
    for (const status of [503, 422, 413, 502, 409]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: `server detail ${status}` }), { status });
      await assert.rejects(tallyApi.readBill(body, "t"), (e: unknown) => e instanceof ApiError && e.status === status && e.message === `server detail ${status}`);
    }
  } finally { globalThis.fetch = original; }
});
