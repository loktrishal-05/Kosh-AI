# Landing page (`/welcome`) quality report

Run on 2026-11-12 against a production build (`next build` then `next start`) in headless Chrome driven over the DevTools protocol. Screenshots were reviewed by eye; the fixes that came out of that review are listed at the end.

## Tests actually run

| Check | Result |
|---|---|
| Unit tests (`npm test`) | 50 pass: frame index clamping, nearest-loaded-frame fallback, beat visibility curve, and English/Hindi/Kannada key parity for every landing string |
| `tsc --noEmit` | clean |
| `next build` | passes; `/welcome` is 115 kB first load (GSAP and Lenis load on demand, after first paint) |
| Console errors while scrolling the whole page at **1440 px** | none |
| Console errors at **390 px** (mobile emulation) | none |
| Console errors with **prefers-reduced-motion** | none; static key frame shown, all text readable in order, no canvas, no Lenis |
| Horizontal page scroll at 1440 / 390 | none |
| **Missing frames** (frames 40 to 79 blocked) | canvas still painted (nearest loaded frame), no errors |
| **Slow network** (400 ms latency, about 400 kbit/s, emulated) | headline present at once; first film frame painted in 1.5 s; no errors. Caveat: measured against localhost, where throttling may be less strict than a real 3G link |
| **Keyboard only** | tab order: skip link, brand, three section links, three language buttons, Sign in; focus outline is solid 3 px |
| **Languages** | English, Hindi and Kannada render with correct scripts; `html lang` follows the picker |

## Not done (be sure to check by hand)

- Real devices: a physical low-cost Android phone, iOS Safari (Lenis and sticky behaviour differ), and a real throttled 3G connection.
- Lighthouse / LCP timing was **not** measured, so there is no LCP number to quote.
- Screen reader pass (VoiceOver / TalkBack / NVDA).
- Hindi and Kannada wording is a first draft awaiting a native speaker.
- 768 px tablet width was not screenshotted separately (the 900 px breakpoint switches to the stacked layout).
- The hero film is now real Veo 3 footage (220 webp frames from one 28 s take, `public/hero/`). The source clips were 640x360, so frames are upscaled to 1280 px and look soft on large screens; regenerate at 1080p for a sharper result. Sign-in backdrop clips are in `public/media/`. Not re-run since the swap: the throttled-network, missing-frame and Hindi/Kannada checks.

## Found by the visual review and fixed

- Headline overlapped the shoebox in the film: the scene is now anchored right (camera scale 0.9 to 0.945) and the headline column is narrower.
- The frame showed as a lighter rectangle against the page: background made flat to match, and the right edge now fades.
- The app's global `main` padding leaked into the landing and pushed the hero down 38 px.
- "GSTR-2B" broke across lines in the statement and flow step.
- The statement ran off screen when the first fix put trailing spaces inside non-wrapping spans.
- The flow line ran below the step circles instead of through them.
- The workbench reveal started as an empty slanted slab; tiles now start visible.
- Favicon 404: added `app/icon.svg`.

## Regenerating the hero frames

`node scripts/hero/render.mjs 220 public/hero` (needs Chrome and ffmpeg on PATH). Output about 3.1 MB.
