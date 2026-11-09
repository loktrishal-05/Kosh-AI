import type { Client } from "./mock.ts";

export function priorityScore(client: Pick<Client, "exceptions" | "deadline">): number {
  // Fixed sandbox clock: 10 points per exception + up to 30 for a nearer deadline.
  const days = Math.ceil((Date.parse(client.deadline + "T00:00:00Z") - Date.parse("2026-11-18T00:00:00Z")) / 86400000);
  return client.exceptions * 10 + Math.max(0, 30 - Math.max(0, days));
}
export function byPriority(a: Client, b: Client): number {
  return priorityScore(b) - priorityScore(a) || a.deadline.localeCompare(b.deadline) || a.id.localeCompare(b.id);
}
