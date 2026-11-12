# Kosh AI: Design Direction (Phase A, awaiting approval)

Status: **proposal.** Nothing in the app has been changed for this yet. Items marked `ASK` need your answer (listed at the end).

## 0. Brief, as I filled it in

| Field | Value |
|---|---|
| App | Kosh AI |
| One sentence | An agentic co-pilot that reads a small business's bills, does the GST/TDS/e-way-bill arithmetic, chases suppliers and explains the result in the owner's language, then stops so a human files. |
| Users | Shop owners on low-cost phones (English, Hindi, Kannada); CAs and accountants at a desk (80-client exception queue). |
| Event / audience | GAVS Tech4Bharat judges (technical merit, entrepreneurial potential), then CAs and investors. |
| Domain world | The Indian neighbourhood shop and its accountant: kirana counters, shoebox of paper bills, the bahi-khata (cloth-bound ledger), brass weights, rubber stamps, WhatsApp. |
| Stack in repo | Next.js 15.5, React 19, plain CSS in `globals.css`, no animation or chart library yet. Python FastAPI behind it. |
| i18n | English, Hindi, Kannada (owner view exists; landing and app chrome do not yet). |
| Looks not to repeat | P2E Bridge: navy `#14213D` + violet `#5B3FD1`, Manrope/Inter, scroll-scrubbed frame-sequence hero. `ASK` if there are others. |
| Deadline / demo length | `ASK` |

Current state to be honest about: the app today is **dark-by-default** (`prefers-color-scheme: dark` flips it) with a green accent and Arial. This direction replaces that with a light theme and new tokens across the whole app, not just the landing page.

## 1. Domain metaphor

**"A shoebox of bills becomes one ruled ledger line, and a human stamps it."**

Scattered paper bills lift out of a shoebox, thin threads connect them to a ruled ledger page, they settle into one clean row, and a vermilion stamp lands on it. The stamp is the product's whole promise: software prepares, a person approves. Every hero beat and transition serves this. Nothing is decorative.

## 2. Three adjectives

**Calm, ledger-precise, quietly warm.**

## 3. Palette (from real materials)

Taken from: bahi-khata page cream, kraft board, ink, rubber-stamp vermilion, leaf green, haldi (turmeric) yellow.

| Token | Hex | Material |
|---|---|---|
| `--ground` | `#F4EEE1` | ledger-page cream |
| `--surface` | `#FBF8F0` | clean cotton paper |
| `--tint` | `#EAE2D0` | kraft / aged page |
| `--ink` | `#1D2421` | green-black ink (not pure black) |
| `--muted` | `#566159` | pencil grey-green |
| `--accent` | `#BC3A22` | rubber-stamp vermilion (the ONE accent) |
| `--success` | `#2F6B4F` | leaf |
| `--warning` | `#8A5A00` | haldi, darkened for text |
| `--haldi-fill` | `#E8A317` | haldi as a non-text fill only |

Shadows are tinted with ink: `0 18px 40px -18px rgba(29,36,33,.28)`, never neutral grey.

**WCAG AA, measured (not estimated):**

| Pair | Ratio |
|---|---|
| ink on ground | 13.69 |
| ink on surface | 14.92 |
| ink on tint | 12.28 |
| muted on ground | 5.59 |
| muted on surface | 6.09 |
| muted on tint | 5.01 |
| white on accent (buttons) | 5.58 |
| accent on ground (links, stamp text) | 4.82 |
| accent on surface | 5.25 |
| success on ground | 5.44 |
| warning on ground | 5.13 |

Every text pair passes 4.5:1. Information is never carried by colour alone: statuses always get a label and an icon.

## 4. Type pairing

- **Display: Fraunces** (soft, high-contrast serif with optical-size and "wonk" axes). It reads like a printed ledger heading and is not used in P2E Bridge. Big, tight, editorial.
- **Text: Instrument Sans.** Calm grotesque that stays out of Fraunces's way and holds up at small sizes.
- **Indic scripts:** neither face has Devanagari or Kannada. Fallback stack is Noto Sans Devanagari and Noto Sans Kannada (large, 20 px minimum on the owner view). I will verify they render before calling the i18n done.
- Scale: 12 / 14 / 16 / 20 / 28 / 44 / 72 / 120 px, display letter-spacing `-0.03em`.

## 5. Hero archetype

**Primary: (a) scroll-scrubbed image sequence on a canvas.** The story is a literal sequence (bills lift, thread, settle, stamp), which is exactly what a scrubbed sequence is good at, and the user controls the pace of the stamp landing.

**Secondary moments (three, deliberately not more):**
1. **Statement reveal** after the hero: one sentence, words rising from 12% to 100% opacity as you scroll ("A shop owner should never need to understand GSTR-2B.").
2. **(h) The real workbench rises out of the page** as live HTML (not a screenshot): the exception matrix tilts from `rotateX(58deg) scale(.72)` to flat, KPI tiles and rows staggering in.
3. **Workflow path draws itself**: the 8-step flow as an SVG path (`pathLength=1`), the "human approves" node in vermilion.

Not used, on purpose: WebGL, horizontal gallery, globe, kinetic type. They don't serve the ledger metaphor and would cost performance on the low-cost phones this product targets.

## 6. Motion signature

- Easing: `expo.out` for entrances (crisp), `power3.inOut` for scrubbed moves (silky). No springs, no bounce.
- Durations: 0.9 to 1.2 s entrances; stagger 0.08 s; ScrollTrigger scrub 0.6.
- Lenis: `lerp: 0.09`, `smoothWheel: true`, one loop driven by `gsap.ticker`.
- **Signature interaction: the stamp.** The final hero frame is the stamp landing. On every primary "Approve" or "Request access" button, the press animates a small vermilion stamp thump (scale 1.08 to 1, 2 px settle, 90 ms), echoing the product's one rule that a human approves. The same thump is used in the app when a draft is approved, so the landing and the product share one gesture.
- Reduced motion: no scrub, no parallax, no autoplay. A static key frame (the stamped ledger) and all text in reading order.

## 7. Reference board (incomplete, stated plainly)

My browser window showed only placeholders on the Awwwards listing, and I did **not** capture 6 to 10 screenshots, so I am not claiming a visual reference board. The techniques I am drawing on, from established practice rather than copied from any single site:
- Apple-style scroll-scrubbed canvas sequences (frame decode and nearest-frame fallback).
- GSAP ScrollTrigger pinned sections and `scrub`.
- Lenis smooth scroll driven from the GSAP ticker.
- Aceternity / Magic UI / React Bits for interaction ideas only (spotlight hover, text reveal), re-skinned to these tokens.
- `ASK`: if you want a real board, tell me and I will do it as a separate step with sites you pick.

## 8. Media plan

See `docs/GENERATION_PROMPTS.md`. **Important constraint found while checking tools:** `agy` (Antigravity CLI) states it cannot generate video, only still images through an Imagen sub-agent. So the three hero clips cannot come from `agy`. Options:

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **A. You generate clips** with Veo / Flow / Runway from my prompts | Real cinematic footage | Best look | Needs you and a video tool; I wait on you |
| **B. I render the hero myself** as a scripted animation (HTML/SVG/canvas to frames with headless Chrome, 220 frames) | Illustrated, ledger-and-paper film | I deliver it end to end, no external tool, no text-in-video problem, tiny file size | Illustrated, not photographic |
| **C. Hybrid** | B now, swap in A's frames later | Ships immediately, upgradeable | Two passes |

Recommendation: **C.** The frame-sequence loader is identical for both, so nothing is thrown away. Logo, icons and the assistant avatar are stills, so `agy`'s Imagen (or Codex) can do those once you approve.

## 9. Build plan after approval (nothing started)

1. Tokens and fonts: replace the dark-default theme in `globals.css` with the light tokens above, app-wide.
2. Landing page, public.
3. Auth pages with video/poster backdrops.
4. Dashboard upgrades: real charts (one library), page transitions, command palette.
5. Quality gates and the tests-run vs manual-checks report.

New dependencies only: `gsap`, `lenis`, one chart library. Commit after each phase.

## Questions for you (`ASK`)

1. **Route:** today `/` is the signed-in CA workbench behind the sign-in gate. Should the public landing take `/` and the workbench move to `/clients`, or should the landing live at `/welcome` and leave `/` alone?
2. **Media:** A, B or C above (I recommend C)?
3. **Accent:** vermilion `#BC3A22` as the single accent, or do you want to keep the current green?
4. **Other previous looks to avoid**, and the **demo length** / deadline.
5. **Scope of the light re-theme:** the whole workbench (Phase D) or landing and auth pages only, for now?
