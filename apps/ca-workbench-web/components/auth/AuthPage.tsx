"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { AUTH, AUTH_LANGS, type AuthLang } from "../../lib/authText";
import { AuthBackdrop, type AuthClip } from "./AuthBackdrop";

export function useAuthLanguage() {
  const [lang, setLang] = useState<AuthLang>("en");
  useEffect(() => { try { const saved = localStorage.getItem("kw-lang"); if (saved === "en" || saved === "hi" || saved === "kn") setLang(saved); } catch { /* storage blocked */ } }, []);
  useEffect(() => {
    try { localStorage.setItem("kw-lang", lang); } catch { /* storage blocked */ }
    document.documentElement.lang = lang;
    return () => { document.documentElement.lang = "en"; };
  }, [lang]);
  return [lang, setLang] as const;
}

export function AuthPage({ lang, onLanguage, clips, signup = false, children }: { lang: AuthLang; onLanguage: (lang: AuthLang) => void; clips: AuthClip[]; signup?: boolean; children: React.ReactNode }) {
  const t = AUTH[lang];
  return <div className={`auth-page ${signup ? "auth-signup" : "auth-signin"}`} lang={lang}>
    <AuthBackdrop clips={clips} />
    <a className="auth-skip" href="#auth-main">{t.skip}</a>
    <header className="auth-header">
      <Link className="auth-brand" href="/welcome"><img src="/icon.svg" width="32" height="32" alt="" /><span>{t.brand}</span></Link>
      <div className="auth-header-actions"><Link className="auth-home" href="/welcome">{t.home}</Link>
        <div className="auth-language" role="group" aria-label={t.language}>{AUTH_LANGS.map(code => <button key={code} type="button" lang={code} aria-pressed={lang === code} onClick={() => onLanguage(code)}>{AUTH[code].languageName}</button>)}</div>
      </div>
    </header>
    <main id="auth-main" className="auth-main">{children}</main>
    <p className="auth-assurance">{t.assurance}</p>
  </div>;
}
