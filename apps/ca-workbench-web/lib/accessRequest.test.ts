import test from "node:test";
import assert from "node:assert/strict";
import { accessMailto } from "./accessRequest.ts";
import { AUTH } from "./authText.ts";

const data = new FormData();
for (const [key, value] of Object.entries({ name: " Asha ", email: "asha@example.org", firm: "Asha & Co", role: "ca", note: "नमस्ते & hello?\r\nBcc: nobody@example.org" })) data.set(key, value);

test("access requests encode the recipient, Unicode and all form details into one email draft", () => {
  const url = new URL(accessMailto(" access+team@example.org ", data, AUTH.en)!);
  assert.equal(decodeURIComponent(url.pathname), "access+team@example.org");
  assert.equal(url.searchParams.get("subject"), AUTH.en.emailSubject);
  assert.equal(url.searchParams.size, 2);
  const body = url.searchParams.get("body")!;
  for (const value of ["Asha", "asha@example.org", "Asha & Co", AUTH.en.roleCA, String(data.get("note")), AUTH.en.consentSummary]) assert.ok(body.includes(value));
});

test("missing or unsafe access addresses cannot open an email draft", () => {
  for (const email of [undefined, "", "  ", "not-an-email", "a@example.org\r\nBcc:x@example.org", "a@example.org?bcc=x@example.org", "a@example.org,b@example.org"]) assert.equal(accessMailto(email, data, AUTH.en), null);
});

test("access email labels and subject follow the selected language", () => {
  for (const t of [AUTH.hi, AUTH.kn]) {
    const url = new URL(accessMailto("access@example.org", data, t)!);
    assert.equal(url.searchParams.get("subject"), t.emailSubject);
    assert.ok(url.searchParams.get("body")!.includes(`${t.role}: ${t.roleCA}`));
  }
});
