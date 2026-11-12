"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { currentSession } from "../lib/session";

/** The API enforces roles and tenants; this gate only decides what to show. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const path = usePathname(), router = useRouter();
  const publicPage = path === "/signin" || path === "/signup" || path === "/welcome";
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    const check = () => { const ok = !!currentSession(); setSignedIn(ok); if (!ok && !publicPage) router.replace("/signin"); };
    check();
    window.addEventListener("focus", check);
    return () => window.removeEventListener("focus", check);
  }, [path, publicPage, router]);
  if (publicPage || signedIn) return <>{children}</>;
  return <section className="empty" role="status"><h1>Checking your sign-in...</h1><p>You will be taken to the sign-in page if you are not signed in.</p></section>;
}
