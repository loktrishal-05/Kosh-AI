import type { Client } from "./mock.ts";
import { formatMoney } from "./money.ts";

export type Lang = "en" | "hi" | "kn";
export const LANGS: { code: Lang; label: string; speech: string }[] = [
  { code: "en", label: "English", speech: "en-IN" }, { code: "hi", label: "हिंदी", speech: "hi-IN" }, { code: "kn", label: "ಕನ್ನಡ", speech: "kn-IN" },
];
// Hindi and Kannada are first drafts for a native speaker to review before real owners see them.
const T = {
  en: {
    title: "Your GST status", due: (n: number, d: string) => `Your GST return is due in ${n} days (${d}).`, ok: "All good. There is nothing you need to do.",
    missing: (n: number) => `${n} supplier bills are not in the government record. We have reminded the suppliers. Until they file, you may lose input credit.`,
    mismatch: (n: number) => `${n} bills have a different amount or number. Your CA will check them.`,
    cash: (p: number) => `Only ${p}% of the tax can be paid from your cash ledger. Add money before the last date.`,
    pay: (a: string) => `Tax to pay this month: ${a}`, safe: "Kosh AI never files a return. You or your CA file it with your own OTP.",
  },
  hi: {
    title: "आपका GST हाल", due: (n: number, d: string) => `आपका GST रिटर्न ${n} दिन में भरना है (${d})।`, ok: "सब ठीक है। आपकी ओर से कुछ करना बाकी नहीं।",
    missing: (n: number) => `${n} सप्लायर के बिल सरकारी रिकॉर्ड में नहीं दिख रहे। हमने सप्लायर को याद दिलाया है। जब तक वे रिटर्न नहीं भरते, आपका इनपुट क्रेडिट रुक सकता है।`,
    mismatch: (n: number) => `${n} बिलों में रकम या नंबर मेल नहीं खा रहा। आपका CA इन्हें जाँचेगा।`,
    cash: (p: number) => `टैक्स का सिर्फ़ ${p}% नकद खाते से चुकाया जा सकता है। आख़िरी तारीख़ से पहले खाते में पैसे जमा करें।`,
    pay: (a: string) => `इस महीने भरने वाला टैक्स: ${a}`, safe: "Kosh AI कभी रिटर्न नहीं भरता। रिटर्न आप या आपके CA अपने OTP से भरते हैं।",
  },
  kn: {
    title: "ನಿಮ್ಮ GST ಸ್ಥಿತಿ", due: (n: number, d: string) => `ನಿಮ್ಮ GST ರಿಟರ್ನ್ ಅನ್ನು ${n} ದಿನಗಳಲ್ಲಿ ಸಲ್ಲಿಸಬೇಕು (${d}).`, ok: "ಎಲ್ಲವೂ ಸರಿಯಾಗಿದೆ. ನೀವು ಏನೂ ಮಾಡಬೇಕಿಲ್ಲ.",
    missing: (n: number) => `${n} ಪೂರೈಕೆದಾರರ ಬಿಲ್‌ಗಳು ಸರ್ಕಾರದ ದಾಖಲೆಯಲ್ಲಿ ಕಾಣಿಸುತ್ತಿಲ್ಲ. ನಾವು ಪೂರೈಕೆದಾರರಿಗೆ ನೆನಪಿಸಿದ್ದೇವೆ. ಅವರು ರಿಟರ್ನ್ ಸಲ್ಲಿಸುವವರೆಗೆ ನಿಮ್ಮ ಇನ್‌ಪುಟ್ ಕ್ರೆಡಿಟ್ ತಡೆಯಾಗಬಹುದು.`,
    mismatch: (n: number) => `${n} ಬಿಲ್‌ಗಳಲ್ಲಿ ಮೊತ್ತ ಅಥವಾ ಸಂಖ್ಯೆ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ನಿಮ್ಮ CA ಅವುಗಳನ್ನು ಪರಿಶೀಲಿಸುತ್ತಾರೆ.`,
    cash: (p: number) => `ತೆರಿಗೆಯ ${p}% ಮಾತ್ರ ನಗದು ಖಾತೆಯಿಂದ ಪಾವತಿಸಲು ಸಾಧ್ಯ. ಕೊನೆಯ ದಿನಾಂಕದ ಮೊದಲು ಖಾತೆಗೆ ಹಣ ಹಾಕಿ.`,
    pay: (a: string) => `ಈ ತಿಂಗಳು ಪಾವತಿಸಬೇಕಾದ ತೆರಿಗೆ: ${a}`, safe: "Kosh AI ಎಂದಿಗೂ ರಿಟರ್ನ್ ಸಲ್ಲಿಸುವುದಿಲ್ಲ. ನೀವು ಅಥವಾ ನಿಮ್ಮ CA ನಿಮ್ಮ OTP ಯಿಂದ ಸಲ್ಲಿಸುತ್ತೀರಿ.",
  },
} as const;

export type Card = { id: string; act: boolean; text: string };

/** What a shop owner needs to hear, in their language: when, what to do, how much, and that a human files. Facts come from the same client record the CA sees. */
export function ownerCards(c: Client, lang: Lang, today: Date): Card[] {
  const t = T[lang], speech = LANGS.find(l => l.code === lang)!.speech;
  const due = new Date(c.deadline + "T00:00:00");
  const days = Math.max(0, Math.ceil((due.getTime() - today.getTime()) / 86400000));
  const mismatched = c.invoices.filter(i => i.status === "MISMATCH" || i.status === "FUZZY").length;
  const cards: Card[] = [{ id: "due", act: days <= 7, text: t.due(days, due.toLocaleDateString(speech, { day: "numeric", month: "long", year: "numeric" })) }];
  if (c.pendingVendor2b) cards.push({ id: "missing", act: true, text: t.missing(c.pendingVendor2b) });
  if (mismatched) cards.push({ id: "mismatch", act: false, text: t.mismatch(mismatched) });
  if (c.cashShortfall) cards.push({ id: "cash", act: true, text: t.cash(c.cashRatioPct) });
  if (cards.length === 1) cards.push({ id: "ok", act: false, text: t.ok });
  cards.push({ id: "pay", act: false, text: t.pay(formatMoney(c.netGstPayablePaise)) }, { id: "safe", act: false, text: t.safe });
  return cards;
}
export const ownerTitle = (lang: Lang) => T[lang].title;
export const LISTEN = { en: ["▶ Listen", "■ Stop"], hi: ["▶ सुनें", "■ रोकें"], kn: ["▶ ಕೇಳಿ", "■ ನಿಲ್ಲಿಸಿ"] } as const;
