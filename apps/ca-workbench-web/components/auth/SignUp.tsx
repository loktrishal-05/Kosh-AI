"use client";
import { useState } from "react";
import Link from "next/link";
import { AUTH } from "../../lib/authText";
import { accessMailto } from "../../lib/accessRequest";
import { AuthPage, useAuthLanguage } from "./AuthPage";

const clips = [{ src: "/media/signin-2.mp4", poster: "/media/signin-2.jpg" }, { src: "/media/signin-1.mp4", poster: "/media/signin-1.jpg" }];
const recipient = process.env.NEXT_PUBLIC_ACCESS_EMAIL;
type FieldError = "required" | "emailInvalid" | "consentRequired";

export function SignUp() {
  const [lang, setLang] = useAuthLanguage(), t = AUTH[lang];
  const [errors, setErrors] = useState<Partial<Record<string, FieldError>>>({}), [status, setStatus] = useState<"" | "draftReady" | "draftFailed" | "unwired">("");
  const wired = !!accessMailto(recipient, new FormData(), t);
  const fieldError = (name: string) => { const error = errors[name]; return error ? <p className="auth-error" id={`access-${name}-error`} role="alert">{t[error]}</p> : null; };

  return <AuthPage lang={lang} onLanguage={setLang} clips={clips} signup>
    <section className="auth-intro" aria-labelledby="signup-title">
      <p className="auth-eyebrow">{t.signupEyebrow}</p><h1 id="signup-title">{t.signupTitle}</h1><p className="auth-lede">{t.signupBody}</p>
      <ul className="auth-benefits">{[[t.benefitBills, t.benefitBillsBody], [t.benefitChecks, t.benefitChecksBody], [t.benefitHuman, t.benefitHumanBody]].map(([title, body]) => <li key={title}><h2>{title}</h2><p>{body}</p></li>)}</ul>
    </section>
    <section className="auth-card" aria-labelledby="access-title">
      <h2 id="access-title">{t.requestAccess}</h2><p className="auth-hint">{t.signupFormBody}</p>
      <form onInvalid={e => {
        const field = e.target as HTMLInputElement;
        setErrors(previous => ({ ...previous, [field.name]: field.name === "consent" ? "consentRequired" : field.validity.typeMismatch ? "emailInvalid" : "required" }));
      }} onChange={e => { const field = e.target as HTMLInputElement; setErrors(previous => ({ ...previous, [field.name]: undefined })); setStatus(""); }} onSubmit={e => {
        e.preventDefault();
        const href = accessMailto(recipient, new FormData(e.currentTarget), t);
        if (!href) { setStatus("unwired"); return; }
        try { window.location.assign(href); setStatus("draftReady"); } catch { setStatus("draftFailed"); }
      }}>
        <div className="auth-fields">
          <div><label htmlFor="access-name">{t.name}</label><input id="access-name" name="name" autoComplete="name" required pattern=".*\S.*" maxLength={100} aria-invalid={!!errors.name} aria-describedby={errors.name ? "access-name-error" : undefined} />{fieldError("name")}</div>
          <div><label htmlFor="access-email">{t.email}</label><input id="access-email" name="email" type="email" autoComplete="email" required maxLength={254} aria-invalid={!!errors.email} aria-describedby={errors.email ? "access-email-error" : undefined} />{fieldError("email")}</div>
          <div><label htmlFor="access-firm">{t.firm}</label><input id="access-firm" name="firm" autoComplete="organization" required pattern=".*\S.*" maxLength={160} aria-invalid={!!errors.firm} aria-describedby={errors.firm ? "access-firm-error" : undefined} />{fieldError("firm")}</div>
          <div><label htmlFor="access-role">{t.role}</label><select id="access-role" name="role" required defaultValue="" aria-invalid={!!errors.role} aria-describedby={errors.role ? "access-role-error" : undefined}><option value="" disabled>{t.chooseRole}</option><option value="ca">{t.roleCA}</option><option value="owner">{t.roleOwner}</option><option value="other">{t.roleOther}</option></select>{fieldError("role")}</div>
        </div>
        <label htmlFor="access-note">{t.note}</label><textarea id="access-note" name="note" rows={3} maxLength={1000} />
        <label className="auth-checkbox" htmlFor="access-consent"><input id="access-consent" name="consent" type="checkbox" required aria-invalid={!!errors.consent} aria-describedby={errors.consent ? "access-consent-error" : undefined} /><span>{t.consent}</span></label>{fieldError("consent")}
        <p className="auth-hint" id="access-email-hint">{t.emailHint}</p>
        {!wired && <p className="auth-notice" role="alert">{t.unwired}</p>}
        <button className="auth-primary" type="submit" aria-describedby="access-email-hint">{t.openDraft}</button>
        {status && (wired || status !== "unwired") && <p className={status === "draftReady" ? "auth-status" : "auth-error"} role={status === "draftReady" ? "status" : "alert"}>{t[status]}</p>}
      </form>
      <p className="auth-switch">{t.alreadyMember} <Link href="/signin">{t.signIn}</Link></p>
    </section>
  </AuthPage>;
}
