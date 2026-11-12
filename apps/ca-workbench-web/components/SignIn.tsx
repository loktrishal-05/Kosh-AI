"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi, type DemoInfo } from "../lib/authApi";
import { currentSession, saveSession } from "../lib/session";
import { AUTH } from "../lib/authText";
import { AuthPage, useAuthLanguage } from "./auth/AuthPage";

type DemoState = { kind: "checking" } | { kind: "on"; info: DemoInfo } | { kind: "off" } | { kind: "unreachable" };
const clips = [{ src: "/media/signin-1.mp4", poster: "/media/signin-1.jpg" }, { src: "/media/signin-2.mp4", poster: "/media/signin-2.jpg" }];

export function SignIn() {
  const router = useRouter();
  const [lang, setLang] = useAuthLanguage(), t = AUTH[lang];
  const [username, setUsername] = useState(""), [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false), [demo, setDemo] = useState<DemoState>({ kind: "checking" });
  const [busy, setBusy] = useState(false), [message, setMessage] = useState<"" | "signingIn" | "demoStarting">(""), [error, setError] = useState("");
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
    setBusy(true); setError(""); setMessage("signingIn");
    try {
      const result = await authApi.login(name, secret);
      saveSession(result.token, result.user);
      router.replace("/");
      setTimeout(() => { if (mounted.current && location.pathname === "/signin") location.assign("/"); }, 2500);      // belt and braces: if the in-app navigation does not happen, go there the plain way
    } catch (e) {
      if (!mounted.current) return;
      setError(e instanceof Error ? e.message : t.signInFailed); setMessage(""); setBusy(false);
    }
  }
  function useDemoAccount() {
    if (demo.kind !== "on" || busy) return;
    const { username: u = "", password: p = "" } = demo.info;
    setUsername(u); setPassword(p); setReveal(true); setError(""); setBusy(true);
    setMessage("demoStarting");
    setTimeout(() => { if (mounted.current) signIn(u, p); }, 800);      // a moment to see the fields fill in; this never depends on anything that can re-render away
  }

  return <AuthPage lang={lang} onLanguage={setLang} clips={clips}>
    <section className="auth-card" aria-labelledby="signin-title">
      <p className="auth-eyebrow">{t.eyebrow}</p><h1 id="signin-title">{t.signInTitle}</h1><p className="auth-hint">{t.signInBody}</p>
      <div className="auth-demo">
        {demo.kind === "on" && <>
          <button type="button" className="auth-demo-button" onClick={useDemoAccount} disabled={busy}>{t.demoButton}</button>
          <p className="auth-hint">{t.demoHint}</p>
        </>}
        {demo.kind === "checking" && <button type="button" className="auth-demo-button" disabled>{t.demoChecking}</button>}
        {demo.kind === "unreachable" && <><p className="auth-error" role="alert">{t.demoUnavailable}</p><button type="button" onClick={loadDemo} disabled={busy}>{t.retry}</button></>}
        {demo.kind === "off" && <p className="auth-hint">{t.demoOff}</p>}
      </div>
      <p className="auth-or">{t.or}</p>
      <form aria-busy={busy} onSubmit={e => { e.preventDefault(); if (!busy) signIn(username.trim(), password); }}>
        <label htmlFor="signin-user">{t.username}</label>
        <input id="signin-user" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} disabled={busy} required maxLength={80} />
        <label htmlFor="signin-pass">{t.password}</label>
        <input id="signin-pass" type={reveal ? "text" : "password"} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} disabled={busy} required maxLength={128} />
        <label className="auth-checkbox"><input type="checkbox" checked={reveal} onChange={e => setReveal(e.target.checked)} />{t.showPassword}</label>
        <button className="auth-primary" type="submit" disabled={busy || !username.trim() || !password}>{busy ? t.signingIn : t.signIn}</button>
      </form>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <p className="auth-status" role="status" aria-live="polite">{message ? t[message] : ""}</p>
      <p className="auth-switch">{t.newHere} <Link href="/signup">{t.requestAccess}</Link></p>
    </section>
  </AuthPage>;
}
