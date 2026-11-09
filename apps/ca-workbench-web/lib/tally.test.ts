import test from "node:test";
import assert from "node:assert/strict";
import { escapeXml, buildTallyXml } from "./tally.ts";
import { clients } from "./mock.ts";

test("all five XML metacharacters are escaped in company, vendor and invoice", () => {
  const value = `A&B<C>D"E'F`;
  const escaped = "A&amp;B&lt;C&gt;D&quot;E&apos;F";
  assert.equal(escapeXml(value), escaped);
  const client = structuredClone(clients[0]);
  client.businessName = value; client.invoices[0].vendor = value; client.invoices[0].register.invoiceNumber = value;
  const xml = buildTallyXml(client);
  for (const tag of ["SVCURRENTCOMPANY", "PARTYLEDGERNAME", "VOUCHERNUMBER"]) assert.ok(xml.includes(`<${tag}>${escaped}</${tag}>`));
});
test("every voucher balances exactly and has matching debit/credit signs", () => {
  for (const client of clients) {
    const xml = buildTallyXml(client);
    const vouchers = [...xml.matchAll(/<VOUCHER\s[^>]*>(.*?)<\/VOUCHER>/g)];
    assert.equal(vouchers.length, client.invoices.length);
    for (const [, voucher] of vouchers) {
      let balance = 0n;
      for (const [, debit, amount] of voucher.matchAll(/<ISDEEMEDPOSITIVE>(Yes|No)<\/ISDEEMEDPOSITIVE><AMOUNT>(-?\d+\.\d{2})<\/AMOUNT>/g)) {
        const paise = BigInt(amount.replace(".", ""));
        assert.equal(debit === "Yes", paise < 0n);
        balance += paise;
      }
      assert.equal(balance, 0n);
      assert.equal([...voucher.matchAll(/<AMOUNT>/g)].length, 3);
    }
  }
});
