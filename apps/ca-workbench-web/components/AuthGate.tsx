"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { currentSession } from "../lib/session";

/** Every page except /signin needs a live session; otherwise the visitor is sent to the sign-in page. (The API enforces roles and tenants on its own: this only decides what to show.) */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const path = usePathname(), router = useRouter();
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    const check = () => { const ok = !!currentSession(); setSignedIn(ok); if (!ok && path !== "/signin") router.replace("/signin"); };
    check();
    window.addEventListener("focus", check);
    return () => window.removeEventListener("focus", check);
  }, [path, router]);
  if (path === "/signin" || signedIn) return <>{children}</>;
  return <section className="empty" role="status"><h1>Checking your sign-in...</h1><p>You will be taken to the sign-in page if you are not signed in.</p></section>;
}
