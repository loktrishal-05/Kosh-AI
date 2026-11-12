"use client";
import { usePathname } from "next/navigation";
import { AuthGate } from "./AuthGate";
import { WorkbenchHeader } from "./WorkbenchHeader";

/** Public pages bring their own navigation; the workbench keeps its chrome and sign-in gate. */
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (path === "/welcome" || path === "/signin" || path === "/signup") return <>{children}</>;
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <WorkbenchHeader />
    <main id="main"><AuthGate>{children}</AuthGate></main>
    <footer>Kosh AI · Client approval stays with the client. <span>Demo workspace / October 2026</span></footer>
  </>;
}
