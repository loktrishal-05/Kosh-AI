"use client";
import { useEffect, useRef, useState } from "react";
import { tallyApi, type Bridge } from "../../lib/tallyApi";

export function BridgePanel({ token, company }: { token: string; company: string }) {
  const [bridges, setBridges] = useState<Bridge[]>([]);
  const [code, setCode] = useState("");
  const [site, setSite] = useState("<this site>");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const result = useRef<HTMLDivElement>(null);
  async function refresh() { setBridges((await tallyApi.bridges(token)).bridges); }
  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await action(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update bridges. Try again."); }
    finally { setBusy(false); requestAnimationFrame(() => result.current?.focus()); }
  }
  useEffect(() => {
    setSite(window.location.origin);
    let active = true;
    setBusy(true);
    tallyApi.bridges(token).then(r => { if (active) setBridges(r.bridges); }).catch(e => { if (active) setMessage(e.message); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [token]);
  useEffect(() => {
    if (!code) return;
    const timer = setTimeout(() => { setCode(""); setMessage("Pairing code expired. Create a new code if needed."); }, 900_000);
    return () => clearTimeout(timer);
  }, [code]);
  return <section className="panel tally-step"><h2>Connect your Tally</h2><p>A bridge is a small program on your Tally computer. It collects only the content you approve here.</p>
    <ol><li>In Tally, open F1 Help &gt; Settings &gt; Advanced Configuration. Turn on the HTTP port and use port 9000. Keep your company open.</li>
    <li>Download the bridge from <code>apps/tally-bridge</code> in the Kosh AI repository onto that computer. Python must be installed.</li>
    <li>Create a pairing code below, then run <code className="tally-code">python tally_bridge.py pair --api {site} --code &lt;code&gt;</code>Replace &lt;code&gt; with your pairing code.</li>
    <li>Run <code>python tally_bridge.py run</code>. Keep it running to collect approved entries.</li></ol>
    <div className="tally-actions"><button disabled={busy || !company.trim() || !!code} onClick={() => run(async () => { setCode((await tallyApi.createBridge(company.trim(), token)).pairing_code); setMessage("Pairing code created. Copy it now; it is shown only in this tab."); await refresh(); })}>Create pairing code</button><button disabled={busy} onClick={() => run(refresh)}>Refresh bridges</button></div>
    <div ref={result} tabIndex={-1} aria-live="polite"><p role="status">{message}</p>{code && <><p>Single-use code · expires in 15 minutes. Treat it like a password.</p><code className="tally-code">{code}</code><div className="tally-actions"><button disabled={busy} onClick={() => run(async () => { await navigator.clipboard.writeText(code); setMessage("Pairing code copied."); })}>Copy pairing code</button><button disabled={busy} onClick={() => setCode("")}>Hide code</button></div></>}</div>
    {bridges.length ? <ul className="tally-list">{bridges.map(bridge => <li key={bridge.bridge_id}><strong>{bridge.company}</strong> · {bridge.revoked ? "Revoked" : bridge.paired ? "Paired" : "Waiting for pairing"}<small>{bridge.host || "Computer not paired"} · Last seen: {bridge.last_seen ? new Date(bridge.last_seen).toLocaleString() : "Never"}</small><button disabled={busy || bridge.revoked} onClick={() => run(async () => { await tallyApi.revokeBridge(bridge.bridge_id, token); setCode(""); setMessage("Bridge revoked. It can no longer collect entries."); await refresh(); })}>Revoke<span className="sr-only"> bridge {bridge.bridge_id}</span></button></li>)}</ul> : <p>{busy ? "Loading bridges…" : "No bridges yet. Create a pairing code to connect your Tally computer."}</p>}
  </section>;
}
