// Offline renderer: serves the project, drives headless Chromium frame by frame
// and pipes PNG frames into FFmpeg. Segments are resumable: a finished segment
// file is skipped on re-run.
//   node scripts/capture.js <h|v> <segStart> <segEnd> [--fps 30] [--seg 6] [--out renders/h]
//   node scripts/capture.js still <h|v> t1,t2,...   -> keyframes/ stills
const http = require('http'), fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const MIME = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.otf': 'font/otf', '.png': 'image/png', '.jpg': 'image/jpeg' };
function serve() {
  return new Promise(res => {
    const s = http.createServer((q, r) => {
      const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
      fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); });
    }).listen(0, () => res(s));
  });
}
async function open(vertical) {
  const srv = await serve();
  const [w, h] = opt('size', vertical ? '1080x1920' : '1920x1080').split('x').map(Number);
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'] });
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text().slice(0, 300)); });
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto(`http://localhost:${srv.address().port}/scenes/render.html`);
  await page.waitForFunction(() => window.setup);
  const info = await page.evaluate(([w, h, v]) => window.setup({ w, h, vertical: v }), [w, h, vertical]);
  return { browser, page, srv, w, h, info };
}
async function frame(page, t) {
  await page.evaluate(t => window.renderFrame(t), t);
  return page.screenshot({ type: 'png', animations: 'disabled', caret: 'hide' });
}
(async () => {
  if (args[0] === 'still') {
    const vertical = args[1] === 'v'; const times = args[2].split(',').map(Number);
    const outDir = path.join(ROOT, opt('out', 'keyframes')); fs.mkdirSync(outDir, { recursive: true });
    const { browser, page, srv } = await open(vertical);
    for (const t of times) {
      const t0 = Date.now(); const png = await frame(page, t);
      const f = path.join(outDir, `${vertical ? 'v' : 'h'}_${t.toFixed(2).padStart(7, '0')}.png`); fs.writeFileSync(f, png);
      console.log(f, Date.now() - t0, 'ms');
    }
    await browser.close(); srv.close(); return;
  }
  const vertical = args[0] === 'v';
  const fps = +opt('fps', 30), segLen = +opt('seg', 6);
  const outDir = path.join(ROOT, opt('out', vertical ? 'renders/v' : 'renders/h')); fs.mkdirSync(outDir, { recursive: true });
  const { browser, page, srv, w, h, info } = await open(vertical);
  const total = Math.round(info.duration * fps);
  const nseg = Math.ceil(total / (segLen * fps));
  const s0 = +(args[1] ?? 0), s1 = Math.min(nseg, +(args[2] ?? nseg));
  for (let s = s0; s < s1; s++) {
    const file = path.join(outDir, `seg_${String(s).padStart(3, '0')}.mp4`);
    if (fs.existsSync(file)) { console.log('skip', file); continue; }
    const f0 = s * segLen * fps, f1 = Math.min(total, (s + 1) * segLen * fps);
    const tmp = file + '.part.mp4';
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', tmp]);
    const t0 = Date.now();
    for (let f = f0; f < f1; f++) {
      const png = await frame(page, (f + 0.5) / fps);
      if (!ff.stdin.write(png)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    fs.renameSync(tmp, file);
    console.log(`seg ${s}/${nseg} frames ${f0}-${f1} ${((Date.now() - t0) / (f1 - f0)).toFixed(0)} ms/frame`);
  }
  await browser.close(); srv.close();
})();
