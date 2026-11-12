"use client";
import { useEffect, useRef, useState } from "react";
import "./auth.css";

export type AuthClip = { src: string; poster: string };

export function AuthBackdrop({ clips }: { clips: AuthClip[] }) {
  const [motion, setMotion] = useState(false), [active, setActive] = useState(0);
  const videos = useRef<(HTMLVideoElement | null)[]>([]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => { setMotion(!media.matches); setActive(0); };
    update(); media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!motion || !clips.length) return;
    const video = videos.current[active];
    if (video) {
      video.currentTime = 0; video.style.opacity = "0";
      video.play().catch(() => { video.style.opacity = "0"; });
    }
    const timer = window.setTimeout(() => setActive(i => (i + 1) % clips.length), 20000);
    return () => { window.clearTimeout(timer); video?.pause(); };
  }, [active, motion, clips]);

  if (!clips.length) return null;
  return <div className="auth-backdrop" aria-hidden="true">
    <img className="auth-poster" src={clips[0].poster} alt="" />
    {motion && clips.map((clip, i) => <div key={clip.src} className="auth-clip" data-active={active === i}>
      <img className="auth-poster" src={clip.poster} alt="" loading={i === 0 ? "eager" : "lazy"} />
      <video ref={el => { videos.current[i] = el; }} src={clip.src} poster={clip.poster} muted playsInline loop={clips.length === 1} preload={i === 0 ? "auto" : "metadata"}
        onPlaying={e => { e.currentTarget.style.opacity = "1"; }} onError={e => { e.currentTarget.style.opacity = "0"; }}
        onEnded={() => { if (active === i) setActive((i + 1) % clips.length); }} />
    </div>)}
    <div className="auth-veil" />
  </div>;
}
