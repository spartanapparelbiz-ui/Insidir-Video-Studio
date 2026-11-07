// Render the terminal promos to 1080x1920 H.264 MP4s.
//   node promo/terminal/render.mjs                 -> every scene
//   node promo/terminal/render.mjs tsla nvda       -> just these
//   node promo/terminal/render.mjs --still 4 tsla  -> PNG of one frame at t=4s
// Needs Playwright (Chromium) and ffmpeg on PATH.
import { spawn, execSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(join(execSync("npm root -g").toString().trim(), "playwright")); }
const { chromium } = pw;
const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "output");
mkdirSync(out, { recursive: true });
const FPS = 30;

const args = process.argv.slice(2);
let still = null;
if (args[0] === "--still") { still = +args[1]; args.splice(0, 2); }
const scenes = args.length ? args : ["tsla", "nvda", "pltr", "semi"];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });

for (const name of scenes) {
  const url = pathToFileURL(join(here, "terminal.html")).href + "?scene=" + name;
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  if (still !== null) {
    await page.evaluate(t => window.render(t), still);
    const f = join(out, `${name}_t${still}.png`);
    await page.screenshot({ path: f });
    console.log(f);
    continue;
  }
  const dur = await page.evaluate(() => window.DURATION);
  const file = join(out, `insidir_terminal_${name}.mp4`);
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-tune", "animation", "-pix_fmt", "yuv420p",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", file], { stdio: ["pipe", "inherit", "inherit"] });
  const n = Math.round(dur * FPS);
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    const buf = await page.screenshot({ type: "png" });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on("close", c => (c === 0 ? res() : rej(new Error("ffmpeg " + c)))));
  console.log(file);
}
await browser.close();
