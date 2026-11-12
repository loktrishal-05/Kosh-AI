"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { clients } from "../lib/mock";
import { LANGS, LISTEN, ownerCards, ownerTitle, type Lang } from "../lib/ownerText";
import { WORKBENCH } from "../lib/workbenchText";
import { ViewState } from "./app/ViewState";

/** The shop owner's page: big type, one idea per card, three languages, spoken aloud on request. One small bundle, with no map, chart or table. */
export function OwnerView() {
  const [lang, setLang] = useState<Lang>("en");
  return <ViewState lang={lang}><OwnerContent lang={lang} setLang={setLang} /></ViewState>;
}
function OwnerContent({ lang, setLang }: { lang: Lang; setLang: (lang: Lang) => void }) {
  const t = WORKBENCH[lang], utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const [idx, setIdx] = useState(Math.min(1, clients.length - 1)), [today] = useState(() => new Date());
  const [canSpeak, setCanSpeak] = useState(false), [speaking, setSpeaking] = useState("");
  const [failed, setFailed] = useState<{ id: string; text: string } | null>(null);
  useEffect(() => { setCanSpeak("speechSynthesis" in window); return () => { utterance.current = null; if ("speechSynthesis" in window) window.speechSynthesis.cancel(); }; }, []);
  const c = clients[idx], speech = LANGS.find(l => l.code === lang)!.speech;
  function stop() { utterance.current = null; window.speechSynthesis?.cancel(); setSpeaking(""); setFailed(null); }
  function listen(id: string, text: string) {
    const wasSpeaking = speaking === id; stop(); if (wasSpeaking) return;
    try {
      const u = new SpeechSynthesisUtterance(text); u.lang = speech; utterance.current = u;
      u.onend = () => { if (utterance.current === u) setSpeaking(""); };
      u.onerror = () => { if (utterance.current === u) { setSpeaking(""); setFailed({ id, text }); } };
      setSpeaking(id); window.speechSynthesis.speak(u);
    } catch { setSpeaking(""); setFailed({ id, text }); }
  }
  if (!c) return <section className="owner panel empty" lang={lang}><h1>{ownerTitle(lang)}</h1><p>{t.emptyOwner}</p><Link className="button-link primary" href="/">{t.clients}</Link></section>;
  const cards = ownerCards(c, lang, today);
  return <section className="owner" lang={lang}>
    <p className="eyebrow">{t.ownerEyebrow}</p>
    <h1>{ownerTitle(lang)}</h1>
    <div className="owner-pick">
      <div role="group" aria-label={t.language}>{LANGS.map(l => <button key={l.code} type="button" aria-pressed={lang === l.code} onClick={() => { stop(); setLang(l.code); }}>{l.label}</button>)}</div>
      <label>{t.business}<select value={idx} onChange={e => { stop(); setIdx(Number(e.target.value)); }}>{clients.slice(0, 10).map((x, i) => <option key={x.id} value={i}>{x.businessName}</option>)}</select></label>
    </div>
    <ul className="owner-cards">{cards.map(k => <li key={k.id} className={k.act ? "owner-card act" : "owner-card"}>
      <p>{k.text}</p>
      {canSpeak && <button type="button" className="owner-listen" aria-pressed={speaking === k.id} onClick={() => listen(k.id, k.text)}>{LISTEN[lang][speaking === k.id ? 1 : 0]}</button>}
    </li>)}</ul>
    {failed && <div className="panel empty" role="alert"><p>{t.speechError}</p><button type="button" onClick={() => listen(failed.id, failed.text)}>{t.retry}</button></div>}
    {!canSpeak && <p className="footnote">{t.speechUnavailable}</p>}
    <p className="footnote">{t.ownerNote}</p>
  </section>;
}
