"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Fraunces, Instrument_Sans, Noto_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";
import { currentSession, endSession, type SessionUser } from "../lib/session";
import { WORKBENCH } from "../lib/workbenchText";
import { CommandPalette } from "./app/CommandPalette";
import { finishViewNavigation, transitionLink } from "./app/navigation";

const display = Fraunces({ subsets: ["latin"], variable: "--f-display", axes: ["opsz", "SOFT"], display: "swap" });
const text = Instrument_Sans({ subsets: ["latin"], variable: "--f-text", display: "swap" });
const hi = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--f-hi", display: "swap" });
const kn = Noto_Sans_Kannada({ subsets: ["kannada"], variable: "--f-kn", display: "swap" });

export function WorkbenchHeader() {
  const path = usePathname(), router = useRouter(), t = WORKBENCH.en;
  const tally = path === "/tally", signin = path === "/signin";
  const [user, setUser] = useState<SessionUser | null>(null);
  const [dark, setDark] = useState(false);
  useEffect(() => { finishViewNavigation(); return finishViewNavigation; }, [path]);
  useEffect(() => {
    let saved = false;
    try { saved = localStorage.getItem("kosh-theme") === "dark"; } catch {}
    setDark(saved); document.documentElement.dataset.theme = saved ? "dark" : "light";
  }, []);
  function toggleTheme() {
    const next = !dark; setDark(next); document.documentElement.dataset.theme = next ? "dark" : "light";
    try { localStorage.setItem("kosh-theme", next ? "dark" : "light"); } catch {}
  }
  useEffect(() => { const s = currentSession(); setUser(s ? (s.user ?? { name: "Signed in", role: "", demo: false }) : null); }, [path]);
  function signOut() { endSession(); setUser(null); router.replace("/signin"); }
  return <><style>{`:root{--f-display:${display.style.fontFamily};--f-text:${text.style.fontFamily};--f-hi:${hi.style.fontFamily};--f-kn:${kn.style.fontFamily}}`}</style>
    <header className="topbar"><Link className="brand" href="/" onClick={event => transitionLink(event, () => router.push("/"))}><span className="brand-mark" aria-hidden="true">K</span> Kosh AI <span className="brand-note">CA WORKBENCH</span></Link>
      {!signin && user && <nav aria-label={t.navigation}>{[["/", t.clients], ["/books", t.books], ["/tally", t.tally], ["/owner", t.owner], ["/impact", t.impact]].map(([href, label]) => <Link key={href} href={href} onClick={event => transitionLink(event, () => router.push(href))} aria-current={(path === href || href === "/" && path.startsWith("/clients/")) ? "page" : undefined}>{label}</Link>)}</nav>}
      <div className="header-tools">{!signin && <CommandPalette />}<button type="button" className="theme-toggle" aria-label={`${t.theme}: ${dark ? t.lightTheme : t.darkTheme}`} aria-pressed={dark} onClick={toggleTheme}>{dark ? t.lightTheme : t.darkTheme}</button></div>
      {!signin && user && <span className="firm">{user.name}{user.role ? ` · ${user.role}` : ""}{user.demo ? " (demo)" : ""} <button type="button" className="signout" onClick={signOut}>Sign out</button></span>}
    </header><div className="sandbox">{signin ? "Evaluation build. Nothing is filed or sent automatically." : path === "/books" ? "Nothing is filed or sent automatically. Choose when to save your books." : tally ? "Nothing reaches your Tally until you approve it. Kosh AI cannot file returns." : "◈ Sandbox data. This console cannot file returns."}</div></>;
}
