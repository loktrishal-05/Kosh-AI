"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { currentSession, endSession, type SessionUser } from "../lib/session";

export function WorkbenchHeader() {
  const path = usePathname(), router = useRouter();
  const tally = path === "/tally", signin = path === "/signin";
  const [user, setUser] = useState<SessionUser | null>(null);
  useEffect(() => { const s = currentSession(); setUser(s ? (s.user ?? { name: "Signed in", role: "", demo: false }) : null); }, [path]);
  function signOut() { endSession(); setUser(null); router.replace("/signin"); }
  return <><header className="topbar"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">T</span> TaxSetu <span className="brand-note">CA WORKBENCH</span></Link>{!signin && user && <nav aria-label="Main navigation"><Link href="/" aria-current={(path === "/" || path.startsWith("/clients/")) ? "page" : undefined}>Clients</Link><Link href="/books" aria-current={path === "/books" ? "page" : undefined}>Books</Link><Link href="/tally" aria-current={tally ? "page" : undefined}>Tally Assistant</Link></nav>}{!signin && user && <span className="firm">{user.name}{user.role ? ` · ${user.role}` : ""}{user.demo ? " (demo)" : ""} <button type="button" className="signout" onClick={signOut}>Sign out</button></span>}</header><div className="sandbox">{signin ? "Evaluation build. Nothing is filed or sent automatically." : path === "/books" ? "Nothing is filed or sent automatically. Choose when to save your books." : tally ? "Nothing reaches your Tally until you approve it. TaxSetu cannot file returns." : "◈ Sandbox data. This console cannot file returns."}</div></>;
}
