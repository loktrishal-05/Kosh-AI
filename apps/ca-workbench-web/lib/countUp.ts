export function countUpFrame(target: number, elapsed: number, duration = 650): number {
  const progress = duration <= 0 ? 1 : Math.min(1, Math.max(0, elapsed / duration));
  return target * (1 - (1 - progress) ** 3);
}
