"use client";
import { useEffect, useState } from "react";
import { clients } from "../lib/mock";
import { LANGS, LISTEN, ownerCards, ownerTitle, type Lang } from "../lib/ownerText";

/** The shop owner's page: big type, one idea per card, three languages, spoken aloud on request. One small bundle, with no map, chart or table. */
export function OwnerView() {
  const [lang, setLang] = useState<Lang>("en"), [idx, setIdx] = useState(1), [today] = useState(() => new Date());
  const [canSpeak, setCanSpeak] = useState(false), [speaking, setSpeaking] = useState("");
  useEffect(() => { setCanSpeak("speechSynthesis" in window); return () => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); }; }, []);
  const c = clients[idx], cards = ownerCards(c, lang, today), speech = LANGS.find(l => l.code === lang)!.speech;
  function listen(id: string, text: string) {
    const s = window.speechSynthesis; s.cancel();
    if (speaking === id) { setSpeaking(""); return; }
    const u = new SpeechSynthesisUtterance(text); u.lang = speech; u.onend = () => setSpeaking(""); u.onerror = () => setSpeaking("");
    setSpeaking(id); s.speak(u);
  }
  return <section className="owner" lang={lang}>
    <p className="eyebrow">FOR THE SHOP OWNER</p>
    <h1>{ownerTitle(lang)}</h1>
    <div className="owner-pick">
      <div role="group" aria-label="Language">{LANGS.map(l => <button key={l.code} type="button" aria-pressed={lang === l.code} onClick={() => { window.speechSynthesis?.cancel(); setSpeaking(""); setLang(l.code); }}>{l.label}</button>)}</div>
      <label>Demo business<select value={idx} onChange={e => setIdx(Number(e.target.value))}>{clients.slice(0, 10).map((x, i) => <option key={x.id} value={i}>{x.businessName}</option>)}</select></label>
    </div>
    <ul className="owner-cards">{cards.map(k => <li key={k.id} className={k.act ? "owner-card act" : "owner-card"}>
      <p>{k.text}</p>
      {canSpeak && <button type="button" className="owner-listen" aria-pressed={speaking === k.id} onClick={() => listen(k.id, k.text)}>{LISTEN[lang][speaking === k.id ? 1 : 0]}</button>}
    </li>)}</ul>
    {!canSpeak && <p className="footnote">Reading aloud needs a phone or browser that supports speech. The text is the same.</p>}
    <p className="footnote">Hindi and Kannada wording is a first draft pending review by a native speaker. Sandbox data.</p>
  </section>;
}
