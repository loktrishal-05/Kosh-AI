/** Illustrative savings model built from the figures in hackathon problem statement 3.1. It is a model with stated assumptions, not a measured result. */
export type ImpactInput = { hoursPerMonth: number; feePerFiling: number; filingsPerYear: number; shareDone: number };

/** The ranges the problem statement gives: 15-20 hours a month, 1,500-3,000 rupees per filing. */
export const STATEMENT = { hoursPerMonth: [15, 20], feePerFiling: [1500, 3000] } as const;

export function impact(i: ImpactInput) {
  const share = Math.min(Math.max(i.shareDone, 0), 0.9);            // ponytail: cap 90% so capacity stays finite; real share must be measured in a pilot
  return {
    hoursSavedMonth: Math.round(i.hoursPerMonth * share * 10) / 10,
    hoursSavedYear: Math.round(i.hoursPerMonth * share * 12),
    feeAtStakeYear: Math.round(i.feePerFiling * i.filingsPerYear * share),
    accountantCapacity: Math.round(10 / (1 - share)) / 10,           // "how many more clients if half the sorting arrived done": 50% -> 2x
  };
}
