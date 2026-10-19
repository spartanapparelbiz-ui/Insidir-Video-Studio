// Headless Motion Canvas render for Insidir Video Studio.
//
//   node scripts/render.mjs --job <folder with data.json + media> --out <video.mp4> [--ffmpeg <path>]
//
// Starts Vite with the Motion Canvas plugin, opens render.html in a headless browser
// (Microsoft Edge on Windows, else Chrome, else Playwright's Chromium), and pipes each
// frame from the canvas straight into FFmpeg. Prints "PROGRESS <done> <total>" lines.

import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
process.env.VITE_CJS_IGNORE_WARNING = 'true';
const {createServer} = await import('vite');
import {chromium} from 'playwright-core';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
}

export async function launchBrowser() {
  const tries = [];
  if (process.env.IVS_BROWSER) tries.push({executablePath: process.env.IVS_BROWSER});
  if (process.platform === 'win32') tries.push({channel: 'msedge'}, {channel: 'chrome'});
  tries.push({}, {channel: 'chrome'}, {channel: 'msedge'});
  let last;
  for (const opt of tries) {
    try {
      return await chromium.launch({headless: true, ...opt});
    } catch (e) {
      last = e;
    }
  }
  throw new Error(
    'No browser found for rendering. Install Microsoft Edge or Google Chrome, or run: ' +
      'npx playwright-core install chromium\n' + (last?.message || ''),
  );
}

async function main() {
  const job = path.resolve(arg('job', ''));
  const out = path.resolve(arg('out', path.join(job, 'motion.mp4')));
  const ffmpegPath = arg('ffmpeg', process.env.INSIDIR_FFMPEG || 'ffmpeg');
  const data = JSON.parse(fs.readFileSync(path.join(job, 'data.json'), 'utf8'));
  const totalFrames = Math.round(data.total * data.fps) + 1;

  process.env.IVS_JOB_DIR = job;
  const server = await createServer({
    root: ROOT,
    configFile: path.join(ROOT, 'vite.config.ts'),
    server: {host: '127.0.0.1', port: 0, strictPort: false},
    clearScreen: false,
  });
  await server.listen();
  const port = server.httpServer.address().port;

  const ff = spawn(ffmpegPath, [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(data.fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '10', '-pix_fmt', 'yuv420p',
    '-r', String(data.fps), out,
  ], {stdio: ['pipe', 'inherit', 'pipe']});
  let ffErr = '';
  ff.stderr.on('data', d => (ffErr += d));
  const ffDone = new Promise(resolve => ff.on('close', resolve));

  const browser = await launchBrowser();
  let result = -1;
  let written = 0;
  try {
    const page = await browser.newPage({viewport: {width: 540, height: 960}});
    page.on('pageerror', e => console.error('page error:', e.message));
    await page.exposeFunction('ivsLog', msg => console.log(msg));
    await page.exposeFunction('ivsFrame', async (_frame, dataUrl) => {
      const buf = Buffer.from(dataUrl.slice(dataUrl.indexOf(',') + 1), 'base64');
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      written++;
      if (written % 15 === 0 || written === totalFrames) console.log(`PROGRESS ${written} ${totalFrames}`);
    });
    await page.exposeFunction('ivsDone', r => {
      result = r;
    });
    // On a cold start Vite optimises dependencies and reloads the page once; wait until
    // the page has stayed put for a moment before starting.
    let navigations = 0;
    page.on('framenavigated', f => {
      if (f === page.mainFrame()) navigations++;
    });
    await page.goto(`http://127.0.0.1:${port}/render.html`);
    for (let attempt = 0; ; attempt++) {
      const seen = navigations;
      try {
        await page.waitForFunction(() => typeof window.ivsStart === 'function', null, {timeout: 180000});
        await page.waitForTimeout(1500);
        if (navigations !== seen) continue;
        await page.evaluate(() => window.ivsStart(), null);
        break;
      } catch (e) {
        if (attempt < 3 && /context was destroyed|navigation/i.test(String(e)) && written === 0) continue;
        throw e;
      }
    }
  } finally {
    ff.stdin.end();
    await browser.close().catch(() => {});
    await server.close();
  }
  const code = await ffDone;
  if (result !== 0) throw new Error(`Motion Canvas render did not finish (result ${result}).`);
  if (code !== 0) throw new Error('FFmpeg failed: ' + ffErr.slice(-1500));
  if (written === 0) throw new Error('No frames were rendered.');
  console.log(`DONE ${written} ${out}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main().catch(e => {
    console.error(e.stack || String(e));
    process.exit(1);
  });
}
