import type { Client } from "./mock.ts";
import { decimalPaise } from "./money.ts";

export function escapeXml(value: string): string {
  return value.replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]!);
}

export function buildTallyXml(client: Client): string {
  const ledger = (name: string, paise: number, debit: boolean) => `<ALLLEDGERENTRIES.LIST><LEDGERNAME>${escapeXml(name)}</LEDGERNAME><ISDEEMEDPOSITIVE>${debit ? "Yes" : "No"}</ISDEEMEDPOSITIVE><AMOUNT>${decimalPaise(paise)}</AMOUNT></ALLLEDGERENTRIES.LIST>`;
  // shortcut: voucher shape is unverified against live TallyPrime; validate ledger mapping before real imports.
  const vouchers = client.invoices.map(invoice => {
    const { taxablePaise, taxPaise, invoiceNumber } = invoice.register;
    const total = taxablePaise + taxPaise;
    if (!Number.isSafeInteger(total) || taxablePaise < 0 || taxPaise < 0) throw new RangeError("Invalid purchase amount");
    return `<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="Purchase" ACTION="Create"><DATE>${invoice.date}</DATE><VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME><VOUCHERNUMBER>${escapeXml(invoiceNumber)}</VOUCHERNUMBER><PARTYLEDGERNAME>${escapeXml(invoice.vendor)}</PARTYLEDGERNAME>${ledger("Purchases", -taxablePaise, true)}${ledger("Input GST", -taxPaise, true)}${ledger(invoice.vendor, total, false)}</VOUCHER></TALLYMESSAGE>`;
  }).join("");
  return `<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>${escapeXml(client.businessName)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>${vouchers}</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>`;
}
