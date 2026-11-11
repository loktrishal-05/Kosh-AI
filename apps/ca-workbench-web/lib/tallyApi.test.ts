import test from "node:test";
import assert from "node:assert/strict";
import { call, tallyApi } from "./tallyApi.ts";

test("API calls use same-origin paths, bearer tokens and the exact approval hash; demo has no auth", async () => {
  const original = globalThis.fetch;
  const requests: { path: string; options: RequestInit | undefined }[] = [];
  globalThis.fetch = async (input, options) => { requests.push({ path: String(input), options }); return new Response("{}", { status: 200 }); };
  try {
    await tallyApi.entry("paid rent", "29");
    await tallyApi.entry("paid rent", "29", "token");
    await tallyApi.approve("batch/id", "a".repeat(64), "token");
    await tallyApi.devToken("tenant", "secret");
    assert.equal(requests[0].path, "/api/v1/tally/sandbox/entry");
    assert.equal(new Headers(requests[0].options?.headers).get("Authorization"), null);
    assert.equal(requests[1].path, "/api/v1/tally/entry");
    assert.equal(new Headers(requests[1].options?.headers).get("Authorization"), "Bearer token");
    assert.equal(requests[2].path, "/api/v1/tally/batches/batch%2Fid/approve");
    assert.deepEqual(JSON.parse(requests[2].options?.body as string), { payload_sha256: "a".repeat(64) });
    assert.equal(new Headers(requests[3].options?.headers).get("X-Admin-Key"), "secret");
    assert.deepEqual(JSON.parse(requests[3].options?.body as string), { tenant_id: "tenant", role: "OWNER" });
  } finally { globalThis.fetch = original; }
});
test("API reports detail and validation errors, tolerates empty bodies, and explains malformed responses", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(null, { status: 204 });
    assert.equal(await call("test"), undefined);
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "the batch changed" }), { status: 409 });
    await assert.rejects(call("test"), /the batch changed/);
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: "company is required" }] }), { status: 422 });
    await assert.rejects(call("test"), /company is required/);
    globalThis.fetch = async () => new Response("", { status: 503 });
    await assert.rejects(call("test"), /503/);
    globalThis.fetch = async () => new Response("<html>oops</html>", { status: 200 });
    await assert.rejects(call("test"), /unreadable/);
    globalThis.fetch = async () => { throw new Error("offline"); };
    await assert.rejects(call("test"), /Cannot reach Kosh AI/);
  } finally { globalThis.fetch = original; }
});
