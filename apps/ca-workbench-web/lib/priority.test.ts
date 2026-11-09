import test from "node:test";
import assert from "node:assert/strict";
import { byPriority, priorityScore } from "./priority.ts";
import { clients } from "./mock.ts";

test("more exceptions and nearer deadlines increase weighted priority", () => {
  const near = { ...clients[0], exceptions: 2, deadline: "2026-11-20" };
  const far = { ...near, deadline: "2027-01-22" };
  const more = { ...near, exceptions: 3 };
  assert.ok(priorityScore(near) > priorityScore(far));
  assert.ok(priorityScore(more) > priorityScore(near));
  assert.deepEqual([far, more, near].sort(byPriority), [more, near, far]);
  const sorted = [...clients].sort(byPriority);
  assert.ok(sorted.every((c, i) => i === 0 || priorityScore(sorted[i - 1]) >= priorityScore(c)));
});
