export type InvoiceStatus = "EXACT" | "FUZZY" | "MISMATCH" | "MISSING_2B";
export type RegisterValues = { invoiceNumber: string; taxablePaise: number; taxPaise: number };
export type Invoice = {
  id: string; vendor: string; date: string; status: InvoiceStatus;
  register: RegisterValues; gstr2b: RegisterValues | null;
  rule37: boolean; rcm: boolean; cashShortfall: boolean;
};
export type Client = {
  id: string; businessName: string; gstin: string; constitution: string;
  filing: "Monthly" | "QRMP"; period: string; deadline: string;
  pendingVendor2b: number; rule37Adjustments: number; rcmAdjustments: number;
  cashShortfall: boolean; cashRatioPct: number; exceptions: number;
  readyToFile: boolean; otpRequested: boolean; netGstPayablePaise: number; invoices: Invoice[];
};

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function generateClients(): Client[] {
  const random = mulberry32(20261109);
  const integer = (max: number) => Math.floor(random() * max);
  const names = ["Shree Ganesh", "Lakshmi", "Patel", "Kaveri", "Mehta", "Sri Balaji", "Gupta", "Malabar", "Annapurna", "Navkar"];
  const trades = ["Textiles", "Engineering Works", "Agro Foods", "Hardware", "Packaging", "Auto Components", "Trading Co.", "Electricals"];
  return Array.from({ length: 80 }, (_, index) => {
    const ready = index % 5 === 0;
    const invoices: Invoice[] = Array.from({ length: 5 + integer(8) }, (_, i) => {
      const status: InvoiceStatus = ready ? "EXACT" : ["MISSING_2B", "FUZZY", "MISMATCH", "EXACT"][i === 0 ? index % 3 : integer(4)] as InvoiceStatus;
      const taxableRupees = 1000 + integer(99000);
      const register = { invoiceNumber: `INV-${index + 101}-${i + 1}`, taxablePaise: taxableRupees * 100, taxPaise: taxableRupees * 18 };
      return {
        id: `${index + 1}-${i + 1}`, vendor: `${names[integer(names.length)]} Supplies & Sons`, date: `202610${String(1 + integer(28)).padStart(2, "0")}`,
        status, register,
        gstr2b: status === "MISSING_2B" ? null : { ...register, invoiceNumber: status === "FUZZY" ? register.invoiceNumber.replace("INV", "INW") : register.invoiceNumber, taxPaise: register.taxPaise + (status === "MISMATCH" ? 12500 : 0) },
        rule37: !ready && i % 4 === 1, rcm: !ready && i % 5 === 2,
        cashShortfall: !ready && index % 3 === 0 && i === 0,
      };
    });
    const pendingVendor2b = invoices.filter(i => i.status === "MISSING_2B").length;
    const rule37Adjustments = invoices.filter(i => i.rule37).length;
    const rcmAdjustments = invoices.filter(i => i.rcm).length;
    const cashShortfall = invoices.some(i => i.cashShortfall);
    // Count each reconciliation issue, adjustment and invoice-linked cash alert once.
    const exceptions = invoices.filter(i => i.status !== "EXACT").length + rule37Adjustments + rcmAdjustments + Number(cashShortfall);
    const filing = index % 4 === 0 ? "QRMP" : "Monthly";
    return {
      id: `ca-${String(index + 1).padStart(3, "0")}`,
      businessName: `${names[index % 10]} ${trades[Math.floor(index / 10)]}`,
      // GSTIN-shaped sandbox identifiers only; checksums are not validated.
      gstin: `27ABCDE${String(1000 + index)}F1Z5`, constitution: ["Proprietorship", "Partnership", "Private Limited"][index % 3],
      filing, period: "October 2026", deadline: filing === "Monthly" ? "2026-11-20" : "2027-01-22",
      pendingVendor2b, rule37Adjustments, rcmAdjustments, cashShortfall,
      cashRatioPct: cashShortfall ? 45 + integer(45) : 100,
      exceptions, readyToFile: exceptions === 0, otpRequested: false,
      netGstPayablePaise: (5000 + integer(180000)) * 100, invoices,
    };
  });
}

export const clients = generateClients();
