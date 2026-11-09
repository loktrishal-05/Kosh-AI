import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = { title: "CA Workbench · TaxSetu", description: "Multi-client compliance exception console — sandbox" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="topbar"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">T</span> TaxSetu <span className="brand-note">CA WORKBENCH</span></Link><span className="firm">Demo CA Associates</span></header>
    <div className="sandbox"><span aria-hidden="true">◈</span> Sandbox data. This console cannot file returns.</div>
    <main id="main">{children}</main>
    <footer>TaxSetu AI · Client approval stays with the client. <span>Demo workspace / October 2026</span></footer>
  </body></html>;
}
