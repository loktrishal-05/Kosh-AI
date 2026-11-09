"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, type DemoInfo } from "../lib/authApi";
import { currentSession, saveSession } from "../lib/session";

export function SignIn() {
  const router = useRouter();
  const [username, setUsername] = useState(""), [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false), [demo, setDemo] = useState<DemoInfo | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [failed, setFailed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (currentSession()) { router.replace("/"); return; }
    let live = true;
    authApi.demoInfo().then(info => { if (live) setDemo(info); }).catch(() => { if (live) setDemo({ enabled: false }); });
    return () => { live = false; clearTimeout(timer.current); };
  }, [router]);

  async function signIn(name: string, secret: string) {
    setBusy(true); setFailed(false); setMessage("Signing you in...");
    try {
      const result = await authApi.login(name, secret);
      saveSession(result.token, result.user);
      router.replace("/");
    } catch (e) {
      setFailed(true); setMessage((e as Error).message); setBusy(false);
    }
  }
  function useDemoAccount() {
    if (!demo?.enabled || busy) return;
    setUsername(demo.username ?? ""); setPassword(demo.password ?? ""); setReveal(true); setFailed(false); setBusy(true);
    setMessage("Demo admin details filled in. Signing you in...");
    timer.current = setTimeout(() => signIn(demo.username ?? "", demo.password ?? ""), 900);     // a moment to see the fields fill in, then the normal sign-in carries on
  }

  return <div className="signin">
    <p className="eyebrow">TAXSETU AI · EVALUATION BUILD</p>
    <h1>Sign in</h1>
    <p>Sign in to open the workbench, the books and the Tally Assistant.</p>
    <section className="panel tally-step" aria-label="Sign in">
      <form onSubmit={e => { e.preventDefault(); if (!busy) signIn(username.trim(), password); }}>
        <label htmlFor="signin-user">Username</label>
        <input id="signin-user" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} disabled={busy} required maxLength={80} />
        <label htmlFor="signin-pass">Password</label>
        <input id="signin-pass" type={reveal ? "text" : "password"} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required maxLength={128} />
        <label className="signin-reveal"><input type="checkbox" checked={reveal} onChange={e => setReveal(e.target.checked)} /> Show password</label>
        <button className="primary signin-submit" type="submit" disabled={busy || !username.trim() || !password}>Sign in</button>
      </form>
      <p className={`signin-message${failed ? " signin-error" : ""}`} role="status" aria-live="polite">{message}</p>
      {demo?.enabled && <div className="signin-demo">
        <p>Evaluating this project? One click signs you in as the demo administrator: no account is needed.</p>
        <button type="button" className="signin-demo-button" onClick={useDemoAccount} disabled={busy}>{demo.label ?? "Demo admin"}</button>
      </div>}
    </section>
  </div>;
}
