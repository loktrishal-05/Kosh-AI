"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function WorkbenchHeader() {
  const tally = usePathname() === "/tally";
  return <><header className="topbar"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">T</span> TaxSetu <span className="brand-note">CA WORKBENCH</span></Link><nav aria-label="Main navigation"><Link href="/" aria-current={!tally ? "page" : undefined}>Clients</Link><Link href="/tally" aria-current={tally ? "page" : undefined}>Tally Assistant</Link></nav><span className="firm">Demo CA Associates</span></header><div className="sandbox">{tally ? "Nothing reaches your Tally until you approve it. TaxSetu cannot file returns." : "◈ Sandbox data. This console cannot file returns."}</div></>;
}
