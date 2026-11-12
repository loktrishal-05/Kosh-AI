/** Helpers for the scroll-scrubbed hero film (220 webp frames in /public/hero). */
export const FRAME_COUNT = 220;
export const frameUrl = (i: number) => `/hero/f_${String(i + 1).padStart(3, "0")}.webp`;

/** Scroll progress 0..1 -> frame index, clamped. */
export function frameAt(progress: number, count = FRAME_COUNT): number {
  return Math.min(count - 1, Math.max(0, Math.round(progress * (count - 1))));
}

/** The closest frame that has actually loaded (so a missing frame never leaves a blank canvas), or -1 if none has. */
export function nearestLoaded(i: number, loaded: ArrayLike<unknown>): number {
  if (loaded[i]) return i;
  for (let d = 1; d < loaded.length; d++) {
    if (i - d >= 0 && loaded[i - d]) return i - d;
    if (i + d < loaded.length && loaded[i + d]) return i + d;
  }
  return -1;
}

/** Trapezoid 0..1: rises over a..b, holds to c, falls over c..d. Drives the story beats. */
export function bump(p: number, a: number, b: number, c: number, d: number): number {
  if (p <= a || p >= d) return 0;
  if (p < b) return (p - a) / (b - a);
  if (p <= c) return 1;
  return 1 - (p - c) / (d - c);
}
