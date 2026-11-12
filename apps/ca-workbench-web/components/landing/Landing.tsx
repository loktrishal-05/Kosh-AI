"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { clients } from "../../lib/mock";
import { priorityScore } from "../../lib/priority";
import { FRAME_COUNT, bump, frameAt, frameUrl, loadFrame, nearestLoaded } from "../../lib/heroFrames";
import { LAND, LAND_LANGS, type LandLang } from "../../lib/landingText";
import "./landing.css";

const REPO = "https://github.com/loktrishal-05/taxsetu-ai";
const PROOF_TARGETS = [974, 3, 107, 3];
const BEAT_CENTERS = [0.22, 0.47, 0.72];

function KMark() { return <svg className="kw-mark" viewBox="0 0 32 32" aria-hidden="true"><rect x="2" y="2" width="28" height="28" rx="8" fill="var(--ink)" /><path d="M11 8v16M11 16l9-8M13.5 14l7 10" stroke="var(--ground)" strokeWidth="2.6" strokeLinecap="round" fill="none" /><circle cx="24.5" cy="8.5" r="3" fill="var(--accent)" /></svg>; }

export function Landing() {
  const [lang, setLang] = useState<LandLang>("en");
  const [reduced, setReduced] = useState<boolean | null>(null);
  const [pct, setPct] = useState(0);
  const t = LAND[lang];
  const root = useRef<HTMLDivElement>(null), hero = useRef<HTMLElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const closing = useRef<HTMLElement>(null), video = useRef<HTMLVideoElement>(null);
  const frames = useRef<(HTMLImageElement | undefined)[]>(new Array(FRAME_COUNT).fill(undefined));
  const redraw = useRef<() => void>(() => {});

  const dash = useMemo(() => {
    const sorted = [...clients].sort((a, b) => priorityScore(b) - priorityScore(a));
    return { total: clients.length, ready: clients.filter(c => c.readyToFile).length, withEx: clients.filter(c => c.exceptions > 0).length, ex: clients.reduce((n, c) => n + c.exceptions, 0), rows: sorted.slice(0, 4) };
  }, []);

  useEffect(() => { try { const s = localStorage.getItem("kw-lang"); if (s === "hi" || s === "kn" || s === "en") setLang(s); } catch { /* storage blocked */ } }, []);
  useEffect(() => { try { localStorage.setItem("kw-lang", lang); } catch { /* storage blocked */ } document.documentElement.lang = lang; }, [lang]);
  useEffect(() => { const m = window.matchMedia("(prefers-reduced-motion: reduce)"); setReduced(m.matches); const f = () => setReduced(m.matches); m.addEventListener("change", f); return () => m.removeEventListener("change", f); }, []);

  // The bar tracks only the opening 12 frames; failures and stalled requests also settle.
  useEffect(() => {
    if (reduced !== false) return;
    let dead = false, done = 0;
    setPct(0);
    const load = async (i: number) => { const im = await loadFrame(i); if (dead) return; if (im) frames.current[i] = im; if (i < 12) setPct(Math.round(++done / 12 * 100)); redraw.current(); };
    (async () => {
      await load(0); if (dead) return; redraw.current();
      await Promise.all(Array.from({ length: 11 }, (_, k) => load(k + 1))); if (dead) return;
      const order = Array.from({ length: FRAME_COUNT - 12 }, (_, k) => k + 12);
      for (let b = 0; b < order.length && !dead; b += 8) {
        await Promise.all(order.slice(b, b + 8).map(load));
      }
    })();
    return () => { dead = true; };
  }, [reduced]);

  useEffect(() => {
    const clip = video.current;
    if (reduced !== false || !clip || !closing.current || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { if (!clip.getAttribute("src")) clip.src = "/media/landing-loop.mp4"; void clip.play().catch(() => {}); }
      else clip.pause();
    }, { rootMargin: "400px 0px" });
    observer.observe(closing.current);
    return () => { observer.disconnect(); clip.pause(); clip.removeAttribute("src"); clip.load(); };
  }, [reduced]);

  useEffect(() => {
    if (reduced === null) return;
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
        root.current!.querySelectorAll<HTMLAnchorElement>("a[data-jump]").forEach(a => {
          const jump = (e: MouseEvent) => {
            const destination = root.current!.querySelector<HTMLElement>(a.hash);
            if (!destination || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button !== 0) return;
            e.preventDefault(); lenis.scrollTo(destination, { offset: -110, onComplete: () => { history.pushState(null, "", a.hash); destination.focus({ preventScroll: true }); } });
          };
          a.addEventListener("click", jump); cleanups.push(() => a.removeEventListener("click", jump));
        });

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
        const film = ScrollTrigger.create({ trigger: hero.current!, start: "top top", end: "bottom bottom", onUpdate: self => { target = self.progress; } });
        target = cur = film.progress;
        const frameTick = () => {
          cur += (target - cur) * 0.14; if (Math.abs(target - cur) < 0.0004) cur = target; draw();
          const lift = Math.min(1, cur / 0.1); intro.style.opacity = String(1 - lift); intro.style.transform = `translateY(${-lift * 60}px) scale(${1 - lift * 0.08})`; intro.inert = lift > 0.6;
          beats.forEach((el, i) => { const v = bump(cur, BEAT_CENTERS[i] - 0.1, BEAT_CENTERS[i] - 0.04, BEAT_CENTERS[i] + 0.04, BEAT_CENTERS[i] + 0.1), dir = cur < BEAT_CENTERS[i] ? 1 : -1; el.style.opacity = String(v); el.style.transform = `translateY(${(1 - v) * 40 * dir}px)`; });
          veil.style.opacity = String(Math.max(0, (cur - 0.9) * 4));
        };
        gsap.ticker.add(frameTick); cleanups.push(() => gsap.ticker.remove(frameTick));
        gsap.fromTo(".kw-intro > *", { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 1.2, ease: "expo.out", stagger: 0.12, delay: 0.15 });
        cleanups.push(() => { intro.removeAttribute("style"); intro.inert = false; beats.forEach(el => el.removeAttribute("style")); veil.removeAttribute("style"); });

        // ---- statement: words rise from faint to ink as they cross the viewport
        gsap.fromTo(q(".kw-word"), { opacity: 0.12 }, { opacity: 1, ease: "none", stagger: 0.1, scrollTrigger: { trigger: ".kw-statement", start: "top 72%", end: "bottom 55%", scrub: 0.6 } });

        // ---- the workbench rises out of the page, then the flow path draws; pinned only where there is room
        const mm = gsap.matchMedia();
        mm.add("(min-width: 900px)", () => {
          gsap.timeline({ scrollTrigger: { trigger: ".kw-rise", start: "top top", end: "+=110%", pin: true, scrub: 0.6 } })
            .fromTo(".kw-dash", { rotateX: 52, scale: 0.82, y: 40 }, { rotateX: 0, scale: 1, y: 0, ease: "power3.inOut", duration: 1 })
            .fromTo(".kw-kpi, .kw-row", { opacity: 0.35, y: 24 }, { opacity: 1, y: 0, ease: "expo.out", stagger: 0.08, duration: 0.6 }, 0.35);
          const section = q<HTMLElement>(".kw-agents")[0], viewport = q<HTMLElement>(".kw-agent-window")[0], track = q<HTMLElement>(".kw-agent-track")[0];
          section.classList.add("kw-agents-pinned");
          const distance = () => Math.max(0, track.scrollWidth - viewport.clientWidth);
          const travel = gsap.to(track, { x: () => -distance(), ease: "none", scrollTrigger: { trigger: section, start: "top top", end: () => `+=${distance()}`, pin: true, scrub: 0.6, invalidateOnRefresh: true } });
          q<HTMLElement>(".kw-agent-card").forEach(card => gsap.fromTo(card, { rotateY: -35 }, { rotateY: 0, ease: "none", scrollTrigger: { trigger: card, containerAnimation: travel, start: "left 95%", end: "left 55%", scrub: 0.6, invalidateOnRefresh: true } }));
          gsap.fromTo(".kw-flow-path", { scaleX: 0, transformOrigin: "left center" }, { scaleX: 1, ease: "none", scrollTrigger: { trigger: ".kw-flow", start: "top 60%", end: "bottom 70%", scrub: 0.6 } });
          return () => section.classList.remove("kw-agents-pinned");
        });
        gsap.from(".kw-step", { opacity: 0, y: 40, duration: 0.9, ease: "expo.out", stagger: 0.08, scrollTrigger: { trigger: ".kw-steps", start: "top 82%", once: true } });
        cleanups.push(() => mm.revert());
        ScrollTrigger.refresh();
        void document.fonts.ready.then(() => { if (!cancelled) ScrollTrigger.refresh(); });
      }, root);
      cleanups.push(() => ctx.revert());
    })();
    return () => { cancelled = true; cleanups.reverse().forEach(f => f()); redraw.current = () => {}; };
  }, [reduced, lang]);

  const words = t.statement.split(" ");
  return <div ref={root} className="kw" lang={lang}>
    <a className="kw-skip" data-jump href="#kw-main">{t.skip}</a>
    <nav className="kw-nav" aria-label={t.navLabel}>
      <Link className="kw-brand" href="/welcome" aria-label={t.homeLabel}><KMark /><span>Kosh AI</span></Link>
      <div className="kw-links"><a data-jump href="#flow">{t.navFlow}</a><a data-jump href="#product">{t.navProduct}</a><a data-jump href="#proof">{t.navProof}</a></div>
      <div className="kw-nav-r">
        <div className="kw-lang" role="group" aria-label={t.languageLabel}>{LAND_LANGS.map(l => <button key={l.code} type="button" aria-pressed={lang === l.code} onClick={() => setLang(l.code)}>{l.label}</button>)}</div>
        <Link className="kw-btn kw-btn-quiet" href="/signin">{t.signIn}</Link>
      </div>
    </nav>

    <main id="kw-main" tabIndex={-1}>
      <section ref={hero} className={reduced !== false ? "kw-hero kw-hero-static" : "kw-hero"} aria-label="Kosh AI">
        <div className="kw-stage">
          {reduced !== false ? <img className="kw-poster" src={frameUrl(FRAME_COUNT - 1)} alt={t.posterLabel} /> : <div className="kw-film"><canvas ref={canvas} role="img" aria-label={t.filmLabel} /></div>}
          <div className="kw-veil" />
          <div className="kw-intro">
            <p className="kw-kicker">{t.kicker}</p>
            <h1><span>{t.h1a}</span> <em>{t.h1b}</em></h1>
            <p className="kw-lede">{t.lede}</p>
            <div className="kw-cta"><Link className="kw-btn kw-btn-primary" href="/signin">{t.demo}</Link><a data-jump className="kw-btn kw-btn-quiet" href="#flow">{t.navFlow}</a></div>
          </div>
          {t.beats.map((b, i) => <p key={i} className="kw-beat"><span>0{i + 1} / 03</span>{b}</p>)}
          {reduced === false && pct < 100 && <div className="kw-load" role="progressbar" aria-label={t.loading} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}><i style={{ transform: `scaleX(${pct / 100})` }} /><span>{t.loading} {pct}%</span></div>}
          {reduced === false && <div className="kw-scrollhint" aria-hidden="true">{t.scroll}</div>}
        </div>
      </section>

      <section className="kw-statement" aria-label={t.statement}><p>{words.map((w, i) => <span key={i}><span className="kw-word">{w}</span>{" "}</span>)}</p></section>

      <section id="product" tabIndex={-1} className="kw-rise" aria-label={t.riseTitle}>
        <div className="kw-rise-in">
          <p className="kw-kicker">{t.riseKicker}</p><h2>{t.riseTitle}</h2><p className="kw-sub">{t.riseBody}</p>
          <div className="kw-persp"><div className="kw-dash" role="img" aria-label={`${t.sandbox} ${dash.total} ${t.kpi[0]}, ${dash.ready} ${t.kpi[1]}, ${dash.withEx} ${t.kpi[2]}`}>
            <div className="kw-dash-bar"><KMark /><b>Kosh AI</b><span>{t.sandbox}</span></div>
            <div className="kw-kpis">{[dash.total, dash.ready, dash.withEx, dash.ex].map((v, i) => <div key={i} className="kw-kpi"><small>{t.kpi[i]}</small><strong>{v}</strong></div>)}</div>
            <div className="kw-rows">{dash.rows.map(c => <div key={c.id} className="kw-row"><span>{c.businessName}<small>{c.gstin}</small></span><span className="kw-bar"><i style={{ width: `${Math.min(100, c.exceptions * 4)}%` }} /></span><b>{c.exceptions}</b><small>{t.due} {c.deadline}</small></div>)}</div>
          </div></div>
        </div>
      </section>

      <section className="kw-agents" aria-labelledby="kw-agents-title">
        <p className="kw-kicker">{t.agentsKicker}</p><h2 id="kw-agents-title">{t.agentsTitle}</h2>
        <div className="kw-agent-window"><ol className="kw-agent-track">{t.agents.map((agent, i) => <li className="kw-agent-card" key={i}><span className="kw-agent-number" aria-hidden="true">0{i + 1} / 05</span><h3>{agent.title}</h3><p>{agent.body}</p></li>)}</ol></div>
      </section>

      <section id="flow" tabIndex={-1} className="kw-flow" aria-label={t.flowTitle}>
        <p className="kw-kicker">{t.flowKicker}</p><h2>{t.flowTitle}</h2>
        <div className="kw-steps">
          <svg className="kw-path" viewBox="0 0 1000 42" preserveAspectRatio="none" aria-hidden="true"><path className="kw-flow-path" d="M0 21 H1000" /></svg>
          <ol>{t.steps.map((s, i) => <li key={i} className={i === 6 ? "kw-step kw-step-human" : "kw-step"}><span>{i + 1}</span>{s}</li>)}</ol>
        </div>
      </section>

      <section id="proof" tabIndex={-1} className="kw-proof" aria-label={t.proofTitle}>
        <p className="kw-kicker">{t.proofKicker}</p><h2>{t.proofTitle}</h2>
        <dl>{PROOF_TARGETS.map((n, i) => <div key={i}><dt data-count={n}>{n}</dt><dd>{t.proof[i]}</dd></div>)}</dl>
        <p className="kw-note">{t.proofNote}</p>
      </section>

      <section ref={closing} className="kw-close" aria-label={t.closeTitle}>
        <video ref={video} className="kw-close-video" poster="/media/landing-loop.jpg" preload="none" muted loop playsInline aria-hidden="true" tabIndex={-1} />
        <div className="kw-close-in"><h2>{t.closeTitle}</h2><p>{t.closeBody}</p><div className="kw-cta"><Link className="kw-btn kw-btn-primary" href="/signin">{t.demo}</Link><a className="kw-btn kw-btn-quiet" href={REPO} rel="noopener noreferrer">{t.code}</a></div></div>
      </section>
    </main>
    <footer className="kw-foot"><span>Kosh AI</span><span>{t.foot}</span></footer>
  </div>;
}
