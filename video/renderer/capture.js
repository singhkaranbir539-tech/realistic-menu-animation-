// Usage: node capture.js <sceneIds comma> [scale] [step]   -> output/scenes/scene_XX.mp4
// or:    node capture.js preview <t1,t2,...> [scale]        -> build/preview_<t>.jpg
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const data = {
  env: JSON.parse(fs.readFileSync(`${ROOT}/build/envelope.json`)),
  timing: JSON.parse(fs.readFileSync(`${ROOT}/build/timing.json`)),
  captions: JSON.parse(fs.readFileSync(`${ROOT}/build/captions.json`)),
  scenes: JSON.parse(fs.readFileSync(`${ROOT}/scenes.json`)),
};
(async () => {
  const browser = await chromium.launch({ args: ['--disable-gpu-vsync'] });
  const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
  page.on('pageerror', e => { console.error('PAGEERR', e.message); process.exit(1); });
  await page.goto('file://' + path.join(__dirname, 'render.html'));
  const mode = process.argv[2];
  const scale = parseFloat(process.argv[mode === 'preview' ? 4 : 3] || '2');
  await page.evaluate(([d, s]) => window.init(d, s), [data, scale]);
  await page.evaluate(() => document.fonts.ready);
  if (mode === 'preview') {
    for (const t of process.argv[3].split(',').map(Number)) {
      const url = await page.evaluate(f => window.frame(f, 0.9), Math.round(t * 30));
      fs.writeFileSync(`${ROOT}/build/preview_${t}.jpg`, Buffer.from(url.split(',')[1], 'base64'));
    }
  } else {
    const scenes = JSON.parse(fs.readFileSync(`${ROOT}/scenes.json`));
    for (const id of mode.split(',').map(Number)) {
      const sc = scenes.find(s => s.id === id);
      const out = `${ROOT}/output/scenes/scene_${String(id).padStart(2, '0')}.mp4`;
      const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', out]);
      const t0 = Date.now();
      for (let f = sc.start * 30; f < sc.end * 30; f++) {
        const url = await page.evaluate(n => window.frame(n, 0.93), f);
        const buf = Buffer.from(url.split(',')[1], 'base64');
        if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
        if (f % 90 === 0) console.log(`scene ${id} frame ${f - sc.start * 30}/${(sc.end - sc.start) * 30} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
      }
      ff.stdin.end(); await new Promise(r => ff.on('close', r));
      console.log('done', out);
    }
  }
  await browser.close();
})();
