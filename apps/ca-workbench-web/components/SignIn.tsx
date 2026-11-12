"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, type DemoInfo } from "../lib/authApi";
import { currentSession, saveSession } from "../lib/session";

type DemoState = { kind: "checking" } | { kind: "on"; info: DemoInfo } | { kind: "off" } | { kind: "unreachable" };

export function SignIn() {
  const router = useRouter();
  const [username, setUsername] = useState(""), [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false), [demo, setDemo] = useState<DemoState>({ kind: "checking" });
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [failed, setFailed] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const loadDemo = useCallback(() => {
    setDemo({ kind: "checking" });
    authApi.demoInfo()
      .then(info => { if (mounted.current) setDemo(info.enabled ? { kind: "on", info } : { kind: "off" }); })
      .catch(() => { if (mounted.current) setDemo({ kind: "unreachable" }); });
  }, []);
  useEffect(() => { if (currentSession()) { router.replace("/"); return; } loadDemo(); }, [router, loadDemo]);

  async function signIn(name: string, secret: string) {
    setBusy(true); setFailed(false); setMessage("Signing you in...");
    try {
      const result = await authApi.login(name, secret);
      saveSession(result.token, result.user);
      router.replace("/");
      setTimeout(() => { if (mounted.current && location.pathname === "/signin") location.assign("/"); }, 2500);      // belt and braces: if the in-app navigation does not happen, go there the plain way
    } catch (e) {
      if (!mounted.current) return;
      setFailed(true); setMessage((e as Error).message); setBusy(false);
    }
  }
  function useDemoAccount() {
    if (demo.kind !== "on" || busy) return;
    const { username: u = "", password: p = "" } = demo.info;
    setUsername(u); setPassword(p); setReveal(true); setFailed(false); setBusy(true);
    setMessage("Demo admin details filled in. Signing you in...");
    setTimeout(() => { if (mounted.current) signIn(u, p); }, 800);      // a moment to see the fields fill in; this never depends on anything that can re-render away
  }

  return <div className="signin">
    <div className="signin-bg" aria-hidden="true">
      <video className="signin-vid signin-vid-a" src="/media/signin-1.mp4" poster="/media/signin-1.jpg" autoPlay muted loop playsInline preload="metadata" />
      <video className="signin-vid signin-vid-b" src="/media/signin-2.mp4" poster="/media/signin-2.jpg" autoPlay muted loop playsInline preload="none" />
    </div>
    <p className="eyebrow">KOSH AI · EVALUATION BUILD</p>
    <h1>Sign in</h1>
    <section className="panel tally-step" aria-label="Sign in">
      <div className="signin-demo">
        {demo.kind === "on" && <>
          <button type="button" className="signin-demo-button" onClick={useDemoAccount} disabled={busy}>{demo.info.label ?? "Demo admin"}: sign in with one click</button>
          <p className="signin-hint">Evaluating this project? This fills in the demo administrator's username and password and signs you in. No account is needed.</p>
        </>}
        {demo.kind === "checking" && <button type="button" className="signin-demo-button" disabled>Demo admin: checking the server...</button>}
        {demo.kind === "unreachable" && <><p className="signin-message signin-error" role="alert">Could not reach the server to set up the demo sign-in.</p><button type="button" onClick={loadDemo}>Try again</button></>}
        {demo.kind === "off" && <p className="signin-hint">The one-click demo is switched off on this server. Sign in with your username and password.</p>}
      </div>
      <p className="signin-or">or sign in with a username and password</p>
      <form onSubmit={e => { e.preventDefault(); if (!busy) signIn(username.trim(), password); }}>
        <label htmlFor="signin-user">Username</label>
        <input id="signin-user" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} disabled={busy} required maxLength={80} />
        <label htmlFor="signin-pass">Password</label>
        <input id="signin-pass" type={reveal ? "text" : "password"} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required maxLength={128} />
        <label className="signin-reveal"><input type="checkbox" checked={reveal} onChange={e => setReveal(e.target.checked)} /> Show password</label>
        <button className="primary signin-submit" type="submit" disabled={busy || !username.trim() || !password}>Sign in</button>
      </form>
      <p className={`signin-message${failed ? " signin-error" : ""}`} role="status" aria-live="polite">{message}</p>
    </section>
  </div>;
}
