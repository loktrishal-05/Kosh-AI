"use client";
import { useEffect, useRef, useState } from "react";
import { countUpFrame } from "../../lib/countUp";

const number = (value: number) => value.toLocaleString("en-IN", { maximumFractionDigits: 1 });
export function CountUp({ value, format = number }: { value: number; format?: (value: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null), started = useRef(false);
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (started.current) { setDisplay(value); return; }
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    function stop() { cancelAnimationFrame(frame); setDisplay(value); }
    function start() {
      if (started.current) return;
      started.current = true;
      if (motion.matches) return;
      const begin = performance.now();
      setDisplay(0);
      function tick(now: number) {
        setDisplay(countUpFrame(value, now - begin));
        if (now - begin < 650) frame = requestAnimationFrame(tick);
      }
      frame = requestAnimationFrame(tick);
    }
    const observer = "IntersectionObserver" in window ? new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { start(); observer?.disconnect(); } }) : null;
    if (observer && ref.current) observer.observe(ref.current); else start();
    motion.addEventListener("change", stop);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); motion.removeEventListener("change", stop); };
  }, [value]);
  return <span ref={ref} aria-label={format(value)}><span aria-hidden="true">{format(display)}</span></span>;
}
