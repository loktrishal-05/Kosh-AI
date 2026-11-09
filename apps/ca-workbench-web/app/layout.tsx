import type { Metadata } from "next";
import { AuthGate } from "../components/AuthGate";
import { WorkbenchHeader } from "../components/WorkbenchHeader";
import "./globals.css";

export const metadata: Metadata = { title: "CA Workbench · TaxSetu", description: "Multi-client compliance exception console — sandbox" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <a className="skip-link" href="#main">Skip to content</a>
    <WorkbenchHeader />
    <main id="main"><AuthGate>{children}</AuthGate></main>
    <footer>TaxSetu AI · Client approval stays with the client. <span>Demo workspace / October 2026</span></footer>
  </body></html>;
}
