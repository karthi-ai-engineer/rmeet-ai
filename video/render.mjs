// Renders the Max film frame by frame (exact timing, no screen recording).
//   node render.mjs                    -> out/video.mp4 (1920x1080, 30 fps, H.264) + out/timeline.json
//   node render.mjs --workers 3        -> render in parallel slices (default 3), then join them losslessly
//   node render.mjs --stills 3,21,37   -> out/stills/t003.0.png ... (quick review)
// Speed: GPU drawing in Chromium (ANGLE/D3D11), JPEG frames (q95) into ffmpeg, parallel slices.
// (NVENC hardware encoding needs NVIDIA driver 610+ with this ffmpeg build; x264 is used.)
import { chromium } from 'playwright';
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, 'out');
mkdirSync(OUT, { recursive: true });
const arg = (k) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };

function findFfmpeg() {
  try { return execSync('where ffmpeg', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().split(/\r?\n/)[0].trim(); } catch { /* not on PATH */ }
  const base = join(process.env.LOCALAPPDATA || '', 'Microsoft', 'WinGet', 'Packages');
  for (const d of existsSync(base) ? readdirSync(base).filter((n) => n.startsWith('Gyan.FFmpeg')) : []) {
    for (const b of readdirSync(join(base, d))) { const p = join(base, d, b, 'bin', 'ffmpeg.exe'); if (existsSync(p)) return p; }
  }
  throw new Error('ffmpeg not found (winget install Gyan.FFmpeg)');
}
const FFMPEG = findFfmpeg();
const run = (args) => new Promise((ok, bad) => { const p = spawn(FFMPEG, args, { stdio: ['ignore', 'inherit', 'inherit'] }); p.on('close', (c) => (c ? bad(new Error(`ffmpeg ${c}`)) : ok())); });

const browser = await chromium.launch({ args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-gpu-rasterization',
  '--enable-zero-copy', '--font-render-hinting=none', '--force-color-profile=srgb'] });
async function openPage() {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(join(HERE, 'film', 'index.html')).href + '?render');
  await page.waitForFunction(() => window.FILM_READY === true, null, { timeout: 60000 });
  await page.evaluate(() => document.fonts.load('600 92px Inter'));
  return page;
}

const first = await openPage();
const film = await first.evaluate(() => window.FILM);
writeFileSync(join(OUT, 'timeline.json'), JSON.stringify(film, null, 1));

const stills = arg('--stills');
if (stills) {
  mkdirSync(join(OUT, 'stills'), { recursive: true });
  for (const s of stills.split(',').map(Number)) {
    await first.evaluate((t) => window.renderAt(t), s);
    await first.screenshot({ path: join(OUT, 'stills', `t${s.toFixed(1).padStart(5, '0')}.png`) });
  }
  console.log(`stills: ${stills}`);
  await browser.close();
  process.exit(0);
}

const fps = film.fps, total = Math.round(film.duration * fps);
const workers = Math.max(1, Number(arg('--workers') ?? 3));
const crf = arg('--crf') ?? '17';
const t0 = Date.now();
let done = 0;
async function slice(page, a, b, file) {
  const ff = spawn(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p', '-tune', 'animation', file], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let f = a; f < b; f++) {
    await page.evaluate((t) => window.renderAt(t), f / fps);
    const jpg = await page.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(jpg)) await new Promise((r) => ff.stdin.once('drain', r));
    if (++done % 150 === 0) console.log(`${done}/${total} frames (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
}
const pages = [first];
for (let i = 1; i < workers; i++) pages.push(await openPage());
const per = Math.ceil(total / workers);
const parts = pages.map((_, i) => join(OUT, `part${i}.mp4`));
await Promise.all(pages.map((p, i) => slice(p, i * per, Math.min(total, (i + 1) * per), parts[i])));
await browser.close();
writeFileSync(join(OUT, 'parts.txt'), parts.map((p) => `file '${p.replace(/\\/g, '/')}'`).join('\n'));
await run(['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(OUT, 'parts.txt'), '-c', 'copy', '-movflags', '+faststart', join(OUT, 'video.mp4')]);
for (const p of [...parts, join(OUT, 'parts.txt')]) rmSync(p, { force: true });
console.log(`done: out/video.mp4 (${total} frames, ${workers} workers, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
