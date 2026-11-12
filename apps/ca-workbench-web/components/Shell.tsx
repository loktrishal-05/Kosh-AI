"use client";
import { usePathname } from "next/navigation";
import { AuthGate } from "./AuthGate";
import { WorkbenchHeader } from "./WorkbenchHeader";

/** The workbench chrome (header, sign-in gate, footer). The public landing page at /welcome brings its own nav and needs no sign-in. */
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (path === "/welcome") return <>{children}</>;
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <WorkbenchHeader />
    <main id="main"><AuthGate>{children}</AuthGate></main>
    <footer>Kosh AI · Client approval stays with the client. <span>Demo workspace / October 2026</span></footer>
  </>;
}
