import test from "node:test";
import assert from "node:assert/strict";
import { AUTH, AUTH_LANGS } from "./authText.ts";

test("auth translations have identical keys and no empty strings", () => {
  for (const lang of AUTH_LANGS) {
    assert.deepEqual(Object.keys(AUTH[lang]).sort(), Object.keys(AUTH.en).sort());
    for (const value of Object.values(AUTH[lang])) assert.ok(value.trim());
  }
});

test("request access explains the email handoff and does not promise an account", () => {
  assert.match(AUTH.en.emailHint, /does not create an account/);
  assert.match(AUTH.en.unwired, /No request has been sent/);
  assert.match(AUTH.en.draftReady, /nothing has been sent/);
});
