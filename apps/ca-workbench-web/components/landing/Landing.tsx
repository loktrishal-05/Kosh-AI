"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Fraunces, Instrument_Sans, Noto_Sans_Devanagari, Noto_Sans_Kannada } from "next/font/google";
import { clients } from "../../lib/mock";
import { priorityScore } from "../../lib/priority";
import { FRAME_COUNT, bump, frameAt, frameUrl, nearestLoaded } from "../../lib/heroFrames";
import { LAND, LAND_LANGS, type LandLang } from "../../lib/landingText";
import "./landing.css";

const display = Fraunces({ subsets: ["latin"], variable: "--f-display", axes: ["opsz", "SOFT"], display: "swap" });
const text = Instrument_Sans({ subsets: ["latin"], variable: "--f-text", display: "swap" });
const hi = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--f-hi", display: "swap" });
const kn = Noto_Sans_Kannada({ subsets: ["kannada"], variable: "--f-kn", display: "swap" });
const REPO = "https://github.com/loktrishal-05/taxsetu-ai";
const PROOF_TARGETS = [974, 3, 107, 3];
const BEAT_CENTERS = [0.22, 0.47, 0.72];

function KMark() { return <svg className="kw-mark" viewBox="0 0 32 32" aria-hidden="true"><rect x="2" y="2" width="28" height="28" rx="8" fill="var(--ink)" /><path d="M11 8v16M11 16l9-8M13.5 14l7 10" stroke="var(--ground)" strokeWidth="2.6" strokeLinecap="round" fill="none" /><circle cx="24.5" cy="8.5" r="3" fill="var(--accent)" /></svg>; }

export function Landing() {
  const [lang, setLang] = useState<LandLang>("en");
  const [reduced, setReduced] = useState(false);
  const [pct, setPct] = useState(0);
  const t = LAND[lang];
  const root = useRef<HTMLDivElement>(null), hero = useRef<HTMLElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const frames = useRef<(HTMLImageElement | undefined)[]>(new Array(FRAME_COUNT).fill(undefined));
  const redraw = useRef<() => void>(() => {});

  const dash = useMemo(() => {
    const sorted = [...clients].sort((a, b) => priorityScore(b) - priorityScore(a));
    return { total: clients.length, ready: clients.filter(c => c.readyToFile).length, withEx: clients.filter(c => c.exceptions > 0).length, ex: clients.reduce((n, c) => n + c.exceptions, 0), rows: sorted.slice(0, 4) };
  }, []);

  useEffect(() => { try { const s = localStorage.getItem("kw-lang"); if (s === "hi" || s === "kn" || s === "en") setLang(s); } catch { /* storage blocked */ } }, []);
  useEffect(() => { try { localStorage.setItem("kw-lang", lang); } catch { /* storage blocked */ } document.documentElement.lang = lang; }, [lang]);
  useEffect(() => { const m = window.matchMedia("(prefers-reduced-motion: reduce)"); setReduced(m.matches); const f = () => setReduced(m.matches); m.addEventListener("change", f); return () => m.removeEventListener("change", f); }, []);

  // frame loading: frame 1 first, then the rest in small batches; failures are tolerated (nearest loaded frame is drawn instead)
  useEffect(() => {
    if (reduced) return;
    let dead = false, done = 0;
    const load = (i: number) => new Promise<void>(res => { const im = new Image(); im.decoding = "async"; im.onload = () => { frames.current[i] = im; res(); }; im.onerror = () => res(); im.src = frameUrl(i); });
    (async () => {
      await load(0); if (dead) return; redraw.current();
      const order = Array.from({ length: FRAME_COUNT - 1 }, (_, k) => k + 1);
      for (let b = 0; b < order.length && !dead; b += 8) {
        await Promise.all(order.slice(b, b + 8).map(load)); done = Math.min(FRAME_COUNT - 1, b + 8);
        setPct(Math.round((done / (FRAME_COUNT - 1)) * 100)); redraw.current();
      }
    })();
    return () => { dead = true; };
  }, [reduced]);

  useEffect(() => {
    let cancelled = false; const cleanups: (() => void)[] = [];
    (async () => {
      const [{ gsap }, { ScrollTrigger }, { default: Lenis }] = await Promise.all([import("gsap"), import("gsap/ScrollTrigger"), import("lenis")]);
      if (cancelled || !root.current) return;
      gsap.registerPlugin(ScrollTrigger);
      const ctx = gsap.context(() => {
        const q = gsap.utils.selector(root.current);
        // proof counters run in every mode; they only need the section to enter
        q<HTMLElement>("[data-count]").forEach(el => {
          const target = Number(el.dataset.count), o = { v: reduced ? target : 0 };
          if (reduced) { el.textContent = String(target); return; }
          gsap.to(o, { v: target, duration: 1.6, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 85%", once: true }, onUpdate: () => { el.textContent = String(Math.round(o.v)); } });
        });
        if (reduced) return;

        const lenis = new Lenis({ lerp: 0.09, smoothWheel: true });
        lenis.on("scroll", ScrollTrigger.update);
        const tick = (time: number) => lenis.raf(time * 1000);
        gsap.ticker.add(tick); gsap.ticker.lagSmoothing(0);
        cleanups.push(() => { gsap.ticker.remove(tick); lenis.destroy(); });
        root.current!.querySelectorAll<HTMLAnchorElement>("a[data-jump]").forEach(a => a.addEventListener("click", e => { e.preventDefault(); lenis.scrollTo(a.getAttribute("href")!, { offset: -20 }); }));

        // ---- hero: scroll progress drives the film and the beats
        const cv = canvas.current!, c2 = cv.getContext("2d")!;
        let target = 0, cur = 0, drawn = -1, size = "";
        const draw = () => {
          const dpr = Math.min(window.devicePixelRatio || 1, 2), w = cv.clientWidth, h = cv.clientHeight, key = `${w}x${h}x${dpr}`;
          if (key !== size) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); size = key; drawn = -1; }
          const want = frameAt(cur), use = nearestLoaded(want, frames.current); if (use < 0 || use === drawn) return;
          const im = frames.current[use]!, s = Math.max(cv.width / im.naturalWidth, cv.height / im.naturalHeight);      // cover, biased right: the action sits in the right two thirds of the footage
          c2.clearRect(0, 0, cv.width, cv.height); c2.drawImage(im, (cv.width - im.naturalWidth * s) * 0.7, (cv.height - im.naturalHeight * s) / 2, im.naturalWidth * s, im.naturalHeight * s); drawn = use;
        };
        redraw.current = () => { drawn = -1; draw(); };
        const intro = root.current!.querySelector<HTMLElement>(".kw-intro")!, beats = [...root.current!.querySelectorAll<HTMLElement>(".kw-beat")];
        const veil = root.current!.querySelector<HTMLElement>(".kw-veil")!;
        ScrollTrigger.create({ trigger: hero.current!, start: "top top", end: "bottom bottom", onUpdate: self => { target = self.progress; } });
        const frameTick = () => {
          cur += (target - cur) * 0.14; if (Math.abs(target - cur) < 0.0004) cur = target; draw();
          const lift = Math.min(1, cur / 0.1); intro.style.opacity = String(1 - lift); intro.style.transform = `translateY(${-lift * 60}px) scale(${1 - lift * 0.08})`; intro.style.filter = `blur(${lift * 14}px)`; intro.style.pointerEvents = lift > 0.6 ? "none" : "auto";
          beats.forEach((el, i) => { const v = bump(cur, BEAT_CENTERS[i] - 0.1, BEAT_CENTERS[i] - 0.04, BEAT_CENTERS[i] + 0.04, BEAT_CENTERS[i] + 0.1), dir = cur < BEAT_CENTERS[i] ? 1 : -1; el.style.opacity = String(v); el.style.filter = `blur(${(1 - v) * 14}px)`; el.style.transform = `translateY(${(1 - v) * 40 * dir}px)`; });
          veil.style.opacity = String(Math.max(0, (cur - 0.9) * 4));
        };
        gsap.ticker.add(frameTick); cleanups.push(() => gsap.ticker.remove(frameTick));
        gsap.fromTo(".kw-intro > *", { opacity: 0, y: 60, filter: "blur(18px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.2, ease: "expo.out", stagger: 0.12, delay: 0.15 });

        // ---- statement: words rise from faint to ink as they cross the viewport
        gsap.fromTo(q(".kw-word"), { opacity: 0.12 }, { opacity: 1, ease: "none", stagger: 0.1, scrollTrigger: { trigger: ".kw-statement", start: "top 72%", end: "bottom 55%", scrub: 0.6 } });

        // ---- the workbench rises out of the page, then the flow path draws; pinned only where there is room
        const mm = gsap.matchMedia();
        mm.add("(min-width: 900px)", () => {
          gsap.timeline({ scrollTrigger: { trigger: ".kw-rise", start: "top top", end: "+=110%", pin: true, scrub: 0.6 } })
            .fromTo(".kw-dash", { rotateX: 52, scale: 0.82, y: 40 }, { rotateX: 0, scale: 1, y: 0, ease: "power3.inOut", duration: 1 })
            .fromTo(".kw-kpi, .kw-row", { opacity: 0.35, y: 24 }, { opacity: 1, y: 0, ease: "expo.out", stagger: 0.08, duration: 0.6 }, 0.35);
          gsap.fromTo(".kw-flow-path", { strokeDashoffset: 1 }, { strokeDashoffset: 0, ease: "none", scrollTrigger: { trigger: ".kw-flow", start: "top 60%", end: "bottom 70%", scrub: 0.6 } });
        });
        mm.add("(max-width: 899px)", () => { gsap.set(".kw-flow-path", { strokeDashoffset: 0 }); });
        gsap.from(".kw-step", { opacity: 0, y: 40, duration: 0.9, ease: "expo.out", stagger: 0.08, scrollTrigger: { trigger: ".kw-steps", start: "top 82%", once: true } });
        cleanups.push(() => mm.revert());
        ScrollTrigger.refresh();
      }, root);
      cleanups.push(() => ctx.revert());
    })();
    return () => { cancelled = true; cleanups.forEach(f => f()); redraw.current = () => {}; };
  }, [reduced]);

  const words = t.statement.split(" ");
  return <div ref={root} className={`kw ${display.variable} ${text.variable} ${hi.variable} ${kn.variable}`} lang={lang}>
    <a className="kw-skip" href="#kw-main">Skip to content</a>
    <nav className="kw-nav" aria-label="Main">
      <Link className="kw-brand" href="/welcome" aria-label="Kosh AI home"><KMark /><span>Kosh AI</span></Link>
      <div className="kw-links"><a data-jump href="#flow">{t.navFlow}</a><a data-jump href="#product">{t.navProduct}</a><a data-jump href="#proof">{t.navProof}</a></div>
      <div className="kw-nav-r">
        <div className="kw-lang" role="group" aria-label="Language">{LAND_LANGS.map(l => <button key={l.code} type="button" aria-pressed={lang === l.code} onClick={() => setLang(l.code)}>{l.label}</button>)}</div>
        <Link className="kw-btn kw-btn-quiet" href="/signin">{t.signIn}</Link>
      </div>
    </nav>

    <main id="kw-main">
      <section ref={hero} className={reduced ? "kw-hero kw-hero-static" : "kw-hero"} aria-label="Kosh AI">
        <div className="kw-stage">
          {reduced ? <img className="kw-poster" src={frameUrl(FRAME_COUNT - 1)} alt="A ledger with bills settled into rows and one vermilion stamp" /> : <div className="kw-film"><canvas ref={canvas} role="img" aria-label="Paper bills lift out of a shoebox, thread into a ledger and a stamp lands on the last row" /></div>}
          <div className="kw-veil" />
          <div className="kw-intro">
            <p className="kw-kicker">{t.kicker}</p>
            <h1><span>{t.h1a}</span> <em>{t.h1b}</em></h1>
            <p className="kw-lede">{t.lede}</p>
            <div className="kw-cta"><Link className="kw-btn kw-btn-primary" href="/signin">{t.demo}</Link><a data-jump className="kw-btn kw-btn-quiet" href="#flow">{t.navFlow}</a></div>
          </div>
          {t.beats.map((b, i) => <p key={i} className="kw-beat"><span>0{i + 1} / 03</span>{b}</p>)}
          {!reduced && pct < 100 && <div className="kw-load" role="status"><i style={{ width: `${pct}%` }} /><span>{t.loading} {pct}%</span></div>}
          {!reduced && <div className="kw-scrollhint" aria-hidden="true">{t.scroll}</div>}
        </div>
      </section>

      <section className="kw-statement" aria-label="Statement"><p>{words.map((w, i) => <span key={i}><span className="kw-word">{w}</span>{" "}</span>)}</p></section>

      <section id="product" className="kw-rise" aria-label="Workbench">
        <div className="kw-rise-in">
          <p className="kw-kicker">{t.riseKicker}</p><h2>{t.riseTitle}</h2><p className="kw-sub">{t.riseBody}</p>
          <div className="kw-persp"><div className="kw-dash" role="img" aria-label={`${dash.total} clients, ${dash.ready} ready to file, ${dash.withEx} with exceptions`}>
            <div className="kw-dash-bar"><KMark /><b>Kosh AI</b><span>{t.sandbox}</span></div>
            <div className="kw-kpis">{[dash.total, dash.ready, dash.withEx, dash.ex].map((v, i) => <div key={i} className="kw-kpi"><small>{t.kpi[i]}</small><strong>{v}</strong></div>)}</div>
            <div className="kw-rows">{dash.rows.map(c => <div key={c.id} className="kw-row"><span>{c.businessName}<small>{c.gstin}</small></span><span className="kw-bar"><i style={{ width: `${Math.min(100, c.exceptions * 4)}%` }} /></span><b>{c.exceptions}</b><small>{t.due} {c.deadline}</small></div>)}</div>
          </div></div>
        </div>
      </section>

      <section id="flow" className="kw-flow" aria-label={t.flowTitle}>
        <p className="kw-kicker">{t.flowKicker}</p><h2>{t.flowTitle}</h2>
        <div className="kw-steps">
          <svg className="kw-path" viewBox="0 0 1000 42" preserveAspectRatio="none" aria-hidden="true"><path className="kw-flow-path" pathLength={1} strokeDasharray={1} strokeDashoffset={1} d="M0 21 H1000" /></svg>
          <ol>{t.steps.map((s, i) => <li key={i} className={i === 6 ? "kw-step kw-step-human" : "kw-step"}><span>{i + 1}</span>{s}</li>)}</ol>
        </div>
      </section>

      <section id="proof" className="kw-proof" aria-label={t.proofTitle}>
        <p className="kw-kicker">{t.proofKicker}</p><h2>{t.proofTitle}</h2>
        <dl>{PROOF_TARGETS.map((n, i) => <div key={i}><dt data-count={n}>{n}</dt><dd>{t.proof[i]}</dd></div>)}</dl>
        <p className="kw-note">{t.proofNote}</p>
      </section>

      <section className="kw-close" aria-label="Try it">
        <img className="kw-close-img" src={frameUrl(FRAME_COUNT - 1)} alt="" loading="lazy" />
        <div className="kw-close-in"><h2>{t.closeTitle}</h2><p>{t.closeBody}</p><div className="kw-cta"><Link className="kw-btn kw-btn-primary" href="/signin">{t.demo}</Link><a className="kw-btn kw-btn-quiet" href={REPO} rel="noopener noreferrer">{t.code}</a></div></div>
      </section>
    </main>
    <footer className="kw-foot"><span>Kosh AI</span><span>{t.foot}</span></footer>
  </div>;
}
