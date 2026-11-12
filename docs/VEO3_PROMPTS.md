# Veo 3 prompts: landing hero and sign-in backdrops

Use these in Google Flow (or Gemini) with Veo 3 / 3.1. Paste the **Shared style block** at the start of every prompt, then the clip prompt.

## Settings

- 16:9, 8 seconds, highest quality (1080p if offered), 24 fps.
- Veo 3 generates audio on its own: say "silent" in the prompt, and I will strip any audio with ffmpeg anyway.
- Generate 3 to 4 variations per clip and keep the **steadiest** one (no camera shake, no jumps, no morphing paper).
- Do not trim or colour-grade the clips; I will do that.
- Drop the files in `apps/ca-workbench-web/public/media/` with the names below.

## Shared style block (paste first, every time)

> Cinematic top-down documentary footage of an old neighbourhood shop counter in India. Soft warm morning daylight from a window on the left, bright airy high-key grade, gentle contrast, fine paper texture, photorealistic, 35 mm look. Colour palette: ledger-page cream (#F4EEE1), cotton white (#FBF8F0), kraft brown (#D6C29B), green-black ink (#1D2421), brass accents, and ONE saturated accent colour only: rubber-stamp vermilion red (#BC3A22). Locked-off tripod camera, perfectly steady, only an extremely slow, smooth push or drift. Composition: all the action sits in the right two thirds of the frame; the left third stays a calm, nearly empty cream counter surface. Silent, no audio, no music, no speech. Do not show: any text, letters, numbers or writing (all paper is blank or has abstract scribbles only), logos, watermarks, subtitles, faces, people, neon, dark moody lighting, lens flares, camera shake, jump cuts, morphing or melting objects.

## Landing hero: three clips that continue each other

For continuity, generate clip 1 first. Take its **last frame** and use it as the **first frame** ("Frames to video") for clip 2, and clip 2's last frame for clip 3. Extract a last frame with:
`ffmpeg -sseof -0.1 -i landing-1.mp4 -frames:v 1 -update 1 last1.png`

### `landing-1.mp4`: the problem (8 s)

> [Shared style block] A scuffed kraft-brown shoebox sits on a worn wooden shop counter, overflowing with a heap of crumpled blank paper bills and receipts. Beside it: a small brass weighing scale, a ballpoint pen, and a steel ink pad with a faint vermilion tint. Over eight seconds the camera performs an almost imperceptible slow push-in. A soft breeze from the window makes a few loose bills gently tremble and one slides a little off the heap; fine dust motes drift through the window light. The mood is calm, slightly cluttered, not dramatic. End on a stable, clean, well-composed frame with the shoebox and its heap still in place, ready to continue.

### `landing-2.mp4`: the transformation (8 s) (first frame = last frame of clip 1)

> [Shared style block] Continue exactly from the first frame. The paper bills lift gently, one after another, off the heap and glide in a graceful line toward an open cloth-bound ledger (green-black cover, cream pages with blank ruled lines) lying on the right of the counter. Thin hairlines of dark ink, with a few in vermilion red, draw taut between each bill and a row of the ledger, like sewing thread being pulled tight. The bills align neatly, flatten and settle into the ruled rows as tidy blank marks. The shoebox is left empty. Smooth, unhurried, precise motion; the camera stays locked with only a very slow drift. End on a clean frame: empty shoebox, ledger with neat filled rows, threads fading away.

### `landing-3.mp4`: resolved, with the stamp (8 s) (first frame = last frame of clip 2)

> [Shared style block] Continue exactly from the first frame. A heavy brass-handled rubber stamp enters from the top right, descends slowly and lands once, softly, on the last row of the ledger with a tiny settle. It leaves one clear, abstract vermilion red ring-and-bars impression (a circle with three short bars inside, NOT letters). The stamp lifts away and leaves the frame. The paper settles and everything becomes still and tranquil. The camera stays locked. End on a calm, finished frame: the ledger with tidy rows and the red impression on the last row.

### `landing-4.mp4` (optional): closing background loop (8 s)

> [Shared style block] The ledger with tidy rows and a vermilion stamp impression rests on the counter. Nothing moves except the window light, which very slowly sweeps across the paper, and a few dust motes drifting. Perfectly locked camera. The last frame must match the first frame so the clip loops seamlessly.

(Loop trick: in Flow, give the same image as both first and last frame. If your version only takes a first frame, tell me and I will loop it with a crossfade in ffmpeg.)

## Sign-in: two calm loops

The sign-in card sits in the **centre** of the screen, so keep the centre bright, soft and quiet; detail only toward the edges. These replace the "right two thirds" composition rule, so for these two **leave out** that sentence from the shared block.

### `signin-1.mp4` (8 s loop)

> [Shared style block, without the composition sentence] A closed cloth-bound ledger with a green-black cover and a small brass key rest on a cream counter, seen from a high angle. Morning window light moves very slowly across the cloth; a few dust motes drift. The centre of the frame is bright, soft and almost empty. Trustworthy, quiet, unhurried. Locked camera. The last frame must match the first frame so it loops seamlessly.

### `signin-2.mp4` (8 s loop)

> [Shared style block, without the composition sentence] A very slow lateral dolly past rows of tidy shelves of bound ledgers in kraft brown and green-black, shallow depth of field, the centre of the frame a soft bright blur of window light. No people. Calm and orderly. The last frame must match the first frame so it loops seamlessly.

## What I do when you give me the files

1. Strip audio, make `.webm` + `.mp4` and a `.jpg` poster for each clip.
2. Join the landing clips and extract about 220 frames (`fps=10`, 1600 px wide, webp), then swap them in for the illustrated hero. Real footage has a different composition from the illustration, so I will re-tune the film's position, mask and the text veil, and check the headline never sits on the busy part.
3. Build the sign-in and sign-up pages with the crossfading backdrop and a light veil, and a still poster under reduced motion.
