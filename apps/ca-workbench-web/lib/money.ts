const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

export function decimalPaise(paise: number): string {
  if (!Number.isSafeInteger(paise)) throw new RangeError("Money must be safe integer paise");
  const amount = BigInt(paise);
  const absolute = amount < 0n ? -amount : amount;
  return `${amount < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

export function formatMoney(paise: number): string {
  // Intl accepts an exact decimal string at runtime; the TS lib still types only number | bigint.
  const exactFormat = rupees.format as unknown as (value: string) => string;
  return exactFormat(decimalPaise(paise));
}
