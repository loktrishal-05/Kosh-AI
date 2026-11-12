// Renders the hero film to webp frames: node scripts/hero/render.mjs <frames> <outDir>  (needs Chrome and ffmpeg on PATH)
import { spawn, spawnSync } from "node:child_process";
import { writeFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const FRAMES = Number(process.argv[2] ?? 220), OUT = resolve(process.argv[3] ?? "public/hero");
const here = dirname(fileURLToPath(import.meta.url));
const tmp = resolve(process.env.TEMP ?? "/tmp", "hero-png"); rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp, { recursive: true }); mkdirSync(OUT, { recursive: true });
const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", ["--headless=new", "--remote-debugging-port=9335", "--user-data-dir=" + resolve(tmp, "profile"), "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let t; for (let i = 0; i < 40; i++) { try { t = await (await fetch("http://127.0.0.1:9335/json")).json(); if (t.length) break; } catch {} await sleep(300); }
const ws = new WebSocket(t.find(x => x.type === "page").webSocketDebuggerUrl); await new Promise(r => (ws.onopen = r));
let id = 0; const p = new Map(); ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && p.has(m.id)) { p.get(m.id)(m.result ?? m); p.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const n = ++id; p.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: pathToFileURL(resolve(here, "hero.html")).href }); await sleep(1500);
for (let i = 0; i < FRAMES; i++) {
  await send("Runtime.evaluate", { expression: `setT(${i / (FRAMES - 1)})` });
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(resolve(tmp, `f_${String(i + 1).padStart(3, "0")}.png`), Buffer.from(r.data, "base64"));
}
ws.close(); chrome.kill();
for (const f of readdirSync(OUT)) if (f.startsWith("f_")) rmSync(resolve(OUT, f));
const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-i", resolve(tmp, "f_%03d.png"), "-c:v", "libwebp", "-quality", "74", "-compression_level", "6", resolve(OUT, "f_%03d.webp")], { stdio: "inherit" });
console.log("frames", FRAMES, "ffmpeg", r.status);
