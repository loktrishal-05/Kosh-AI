import test from "node:test";
import assert from "node:assert/strict";
import type { MouseEvent } from "react";
import { finishViewNavigation, navigateView, transitionLink } from "../components/app/navigation.ts";

test("view transitions wait for route commit and skip reduced motion, unsupported browsers and same route", async () => {
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window"), originalDocument = Object.getOwnPropertyDescriptor(globalThis, "document"), originalRaf = Object.getOwnPropertyDescriptor(globalThis, "requestAnimationFrame");
  let reduced = false, transitions = 0, navigations = 0, snapshot: Promise<void> | undefined;
  const doc: { startViewTransition?: (update: () => Promise<void>) => { finished: Promise<void> } } = { startViewTransition: update => { transitions++; snapshot = update(); return { finished: snapshot }; } };
  Object.defineProperty(globalThis, "window", { configurable: true, value: { location: { pathname: "/" }, matchMedia: () => ({ matches: reduced }) } });
  Object.defineProperty(globalThis, "document", { configurable: true, value: doc });
  Object.defineProperty(globalThis, "requestAnimationFrame", { configurable: true, value: (callback: () => void) => { callback(); return 1; } });
  try {
    navigateView("/impact", () => navigations++);
    let committed = false; void snapshot!.then(() => { committed = true; });
    await Promise.resolve(); assert.equal(committed, false);
    finishViewNavigation(); await snapshot; assert.equal(committed, true);
    navigateView("/", () => navigations++);
    reduced = true; navigateView("/owner", () => navigations++);
    reduced = false; delete doc.startViewTransition; navigateView("/books", () => navigations++);
    const event = { ctrlKey: true, preventDefault: () => assert.fail("modified click must stay native") } as unknown as MouseEvent<HTMLAnchorElement>;
    transitionLink(event, () => assert.fail("modified click must stay native"));
    assert.equal(transitions, 1); assert.equal(navigations, 4);
  } finally {
    for (const [name, descriptor] of [["window", originalWindow], ["document", originalDocument], ["requestAnimationFrame", originalRaf]] as const) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor); else Reflect.deleteProperty(globalThis, name);
    }
  }
});
