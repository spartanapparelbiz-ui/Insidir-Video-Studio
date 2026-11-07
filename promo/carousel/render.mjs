// Render the carousel to PNGs in two sizes:
//   output/4x5/slide-N.png   1080x1350 (Instagram feed carousel)
//   output/9x16/slide-N.png  1080x1920 (TikTok photo mode, Reels/Stories)
//   node promo/carousel/render.mjs
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(join(execSync("npm root -g").toString().trim(), "playwright")); }
const here = dirname(fileURLToPath(import.meta.url));
const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
for (const [name, h] of [["4x5", 1350], ["9x16", 1920]]) {
  const dir = join(here, "output", name);
  mkdirSync(dir, { recursive: true });
  await page.goto(pathToFileURL(join(here, "slides.html")).href + "?h=" + h);
  await page.evaluate(() => document.fonts.ready);
  const slides = await page.$$(".slide");
  for (let i = 0; i < slides.length; i++) {
    const f = join(dir, `slide-${i + 1}.png`);
    await slides[i].screenshot({ path: f });
    console.log(f);
  }
}
await browser.close();
