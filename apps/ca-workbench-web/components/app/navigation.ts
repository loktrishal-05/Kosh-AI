"use client";
import type { MouseEvent } from "react";

let routeCommitted: (() => void) | undefined;
export function finishViewNavigation() { routeCommitted?.(); }
export function navigateView(href: string, navigate: () => void) {
  if (href !== window.location.pathname && typeof document.startViewTransition === "function" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    routeCommitted?.();
    const transition = document.startViewTransition(() => new Promise<void>(resolve => {
      const finish = () => { clearTimeout(timeout); if (routeCommitted === commit) routeCommitted = undefined; resolve(); };
      const commit = () => requestAnimationFrame(finish);
      const timeout = setTimeout(finish, 3000);
      routeCommitted = commit;
      navigate();
    }));
    void transition.finished.catch(() => {});
  } else navigate();
}
export function transitionLink(event: MouseEvent<HTMLAnchorElement>, navigate: () => void) {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.currentTarget.target === "_blank") return;
  if (typeof document.startViewTransition === "function" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) { event.preventDefault(); navigateView(new URL(event.currentTarget.href).pathname, navigate); }
}
