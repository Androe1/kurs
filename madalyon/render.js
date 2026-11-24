// madalyon.html'i başsız Chromium'da kare kare çizip ffmpeg ile MP4'e çevirir.
// Kullanım: node render.js [çıktı.mp4] [--fps 60] [--still 6.0] [--three <three paketi dizini>]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path'), fs = require('fs');
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const out = args[0] && !args[0].startsWith('--') ? args[0] : path.join(__dirname, '..', 'output', 'madalyonun_iki_yuzu.mp4');
const fps = +opt('--fps', 60), W = +opt('--w', 1920), H = +opt('--h', 1080), pr = opt('--pr', '1');
const still = opt('--still'), threeDir = opt('--three', path.join(__dirname, 'node_modules', 'three'));

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => console.log('[err]', e.stack));
  await page.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**', r => {
    const rel = new URL(r.request().url()).pathname.replace('/npm/three@0.160.0/', '');
    r.fulfill({ path: path.join(threeDir, rel), contentType: 'application/javascript' });
  });
  const url = 'file://' + path.join(__dirname, 'madalyon.html') + `?render&pr=${pr}` + (still ? `&t=${still}` : '');
  await page.goto(url);
  await page.waitForFunction('window.__ready === true', null, { timeout: 120000 });
  if (still) {
    const ts = still.split(',');
    for (const t of ts) {
      await page.evaluate(t => window.renderAt(t), +t);
      const f = out.replace(/\.(mp4|png)$/, '') + `_${t}.png`;
      await page.screenshot({ path: f }); console.log(f);
    }
    return browser.close();
  }
  const dur = await page.evaluate(() => window.DURATION), n = Math.round(dur * fps);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.renderAt(t), i / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 96 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 60 === 0) console.log(`kare ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log('yazıldı:', out);
})();
