import type { Metadata } from "next";
import { AuthGate } from "../components/AuthGate";
import { WorkbenchHeader } from "../components/WorkbenchHeader";
import "./globals.css";

export const metadata: Metadata = { title: "CA Workbench · Kosh AI", description: "Multi-client compliance exception console — sandbox" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <a className="skip-link" href="#main">Skip to content</a>
    <WorkbenchHeader />
    <main id="main"><AuthGate>{children}</AuthGate></main>
    <footer>Kosh AI · Client approval stays with the client. <span>Demo workspace / October 2026</span></footer>
  </body></html>;
}
