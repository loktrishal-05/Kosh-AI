import type { Metadata } from "next";
import { Fraunces, Instrument_Sans, Noto_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";
import { Shell } from "../components/Shell";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--f-display", axes: ["opsz", "SOFT"], display: "swap" });
const text = Instrument_Sans({ subsets: ["latin"], variable: "--f-text", display: "swap" });
const hi = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--f-hi", display: "swap" });
const kn = Noto_Sans_Kannada({ subsets: ["kannada"], variable: "--f-kn", display: "swap" });

export const metadata: Metadata = { title: "CA Workbench · Kosh AI", description: "Multi-client compliance exception console — sandbox" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${display.variable} ${text.variable} ${hi.variable} ${kn.variable}`}>
    <Shell>{children}</Shell>
  </body></html>;
}
