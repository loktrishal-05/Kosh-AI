import test from "node:test";
import assert from "node:assert/strict";
import { fuzzyFilter } from "./commands.ts";

const routes = [{ href: "/", label: "Clients" }, { href: "/impact", label: "Impact" }, { href: "/clients/ca-001", label: "Shree Ganesh Textiles", keywords: "27ABCDE1000F1Z5" }, { href: "/books", label: "खाते" }];
test("palette matches ordered letters, routes, client IDs and GSTINs", () => {
  assert.deepEqual(fuzzyFilter(routes, "  "), routes);
  assert.equal(fuzzyFilter(routes, "IMPT")[0].href, "/impact");
  assert.equal(fuzzyFilter(routes, "ca-001")[0].href, "/clients/ca-001");
  assert.equal(fuzzyFilter(routes, "27abc")[0].href, "/clients/ca-001");
  assert.equal(fuzzyFilter(routes, "खाते")[0].href, "/books");
  assert.deepEqual(fuzzyFilter(routes, "zzzz"), []);
  assert.deepEqual(fuzzyFilter(routes, "tpmI"), []);
});
test("palette ranks contiguous matches first and leaves source order unchanged", () => {
  const commands = [{ href: "/1", label: "Client mapping" }, { href: "/2", label: "Impact" }, { href: "/3", label: "Impact" }];
  assert.deepEqual(fuzzyFilter(commands, "imp").map(c => c.href), ["/2", "/3", "/1"]);
  assert.equal(commands[0].href, "/1");
});
