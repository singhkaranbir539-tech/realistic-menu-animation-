// 2D motion-graphics layer drawn over the graded 3D frame.
// Tracking callouts are anchored to projected 3D points of the active camera.
import * as THREE from 'three';
import { clamp, ease, smooth } from './lib.js';

const ACCENT = '#7fd6e6', WARM = '#ffb08a', WHITE = 'rgba(245,247,250,';
const v = new THREE.Vector3();

function fade(lt, a, b, fin = 0.45, fout = 0.35) { return smooth(a, a + fin, lt) * (1 - smooth(b - fout, b, lt)); }

function project(cam, p, W, H) {
  v.set(...p).project(cam);
  return { x: (v.x * .5 + .5) * W, y: (-v.y * .5 + .5) * H, behind: v.z > 1 };
}

function font(ctx, size, weight = 500) { ctx.font = `${weight} ${size}px Inter`; }

function callout(ctx, L, s, cam, lt, dur, W, H, VERT, anchors) {
  const t0 = (L.at?.[0] ?? 0.08) * dur, t1 = (L.at?.[1] ?? 0.95) * dur;
  const a = fade(lt, t0, t1);
  if (a <= 0.001) return;
  const ap = L.at3 ? (anchors[L.at3] ? anchors[L.at3]() : null) : L.anchor;
  const pr = ap ? project(cam, ap, W, H) : { x: (L.screen[0]) * W, y: L.screen[1] * H };
  if (pr.behind) return;
  if (!ap && L.len === 0) { // centred caption (no leader)
    const u0 = H / 1080, ts0 = (L.size ?? 34) * u0 * (VERT ? 1.3 : 1); const k0 = ease.out(clamp((lt - t0) / 0.7));
    ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center'; ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 14 * u0;
    font(ctx, ts0, 300); ctx.letterSpacing = `${(10 - 6 * k0) * u0}px`; ctx.fillStyle = WHITE + '0.97)';
    const cy0 = VERT ? H * 0.2 : pr.y; ctx.fillText(L.text.toUpperCase(), pr.x, cy0);
    ctx.fillStyle = 'rgba(127,214,230,0.85)'; const bw0 = 120 * u0 * k0; ctx.fillRect(pr.x - bw0 / 2, cy0 + 16 * u0, bw0, 1.6 * u0);
    if (L.sub) { font(ctx, ts0 * 0.55, 400); ctx.letterSpacing = `${1 * u0}px`; ctx.fillStyle = 'rgba(200,220,228,0.9)'; ctx.fillText(L.sub, pr.x, cy0 + 16 * u0 + ts0 * 0.85); }
    ctx.restore(); return;
  }
  const u = H / 1080;
  const side = L.side ?? (pr.x > W * 0.55 ? -1 : 1);
  const lineLen = (L.len ?? 140) * u * (VERT ? 0.8 : 1);
  const rise = (L.rise ?? -70) * u;
  const k = ease.out(clamp((lt - t0) / 0.6));
  const ex = pr.x + side * lineLen * 0.45 * k, ey = pr.y + rise * k;
  let fx = ex + side * lineLen * 0.55 * k;
  const fy = ey;
  const pad = 70 * u;
  fx = clamp(fx, pad, W - pad);
  ctx.save(); ctx.globalAlpha = a;
  // anchor ring
  ctx.strokeStyle = L.warm ? WARM : ACCENT; ctx.lineWidth = 1.6 * u;
  ctx.beginPath(); ctx.arc(pr.x, pr.y, 7 * u * (0.6 + 0.4 * k), 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = L.warm ? WARM : ACCENT; ctx.beginPath(); ctx.arc(pr.x, pr.y, 2.4 * u, 0, Math.PI * 2); ctx.fill();
  // leader
  ctx.strokeStyle = 'rgba(235,245,250,0.75)'; ctx.lineWidth = 1.2 * u;
  ctx.beginPath(); ctx.moveTo(pr.x + side * 8 * u, pr.y - 4 * u); ctx.lineTo(ex, ey); ctx.lineTo(fx, fy); ctx.stroke();
  // text
  const ts = (L.size ?? 30) * u * (VERT ? 1.25 : 1);
  ctx.textAlign = side > 0 ? 'left' : 'right';
  ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 10 * u;
  const tx = fx + side * 12 * u;
  const reveal = clamp((lt - t0 - 0.25) / 0.5);
  font(ctx, ts, 600); ctx.letterSpacing = `${1.5 * u}px`;
  ctx.fillStyle = WHITE + (0.96 * reveal) + ')';
  ctx.fillText(L.text.toUpperCase(), tx, fy - 10 * u);
  if (L.sub) { font(ctx, ts * 0.62, 400); ctx.letterSpacing = `${0.5 * u}px`; ctx.fillStyle = `rgba(190,215,225,${0.85 * reveal})`; ctx.fillText(L.sub, tx, fy + ts * 0.62 + 4 * u); }
  ctx.restore();
}

function title(ctx, T, lt, dur, W, H, VERT) {
  const t0 = T.at?.[0] ?? 0.3, t1 = T.at?.[1] ?? Math.min(dur, 3.6);
  const a = fade(lt, t0, t1, 0.6, 0.6);
  if (a <= 0) return;
  const u = H / 1080;
  const s = (T.size ?? 64) * u * (VERT ? 0.95 : 1);
  ctx.save(); ctx.globalAlpha = a; ctx.textAlign = 'center';
  const cx = W / 2, cy = VERT ? H * 0.2 : H * (T.y ?? 0.44);
  const k = ease.expoOut(clamp((lt - t0) / 1.4));
  ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 24 * u;
  if (T.kicker) { font(ctx, s * 0.3, 600); ctx.letterSpacing = `${6 * u}px`; ctx.fillStyle = ACCENT; ctx.fillText(T.kicker.toUpperCase(), cx, cy - s * 0.95); }
  font(ctx, s, 300); ctx.letterSpacing = `${(14 - 8 * k) * u}px`; ctx.fillStyle = WHITE + '0.97)';
  const lines = VERT && T.vlines ? T.vlines : [T.text];
  lines.forEach((ln, i) => ctx.fillText(ln.toUpperCase(), cx, cy + i * s * 1.15));
  const bw = 220 * u * k; ctx.fillStyle = 'rgba(127,214,230,0.8)'; ctx.fillRect(cx - bw / 2, cy + (lines.length - 1) * s * 1.15 + s * 0.45, bw, 2 * u);
  ctx.restore();
}

function note(ctx, N, lt, dur, W, H, VERT) {
  const a = fade(lt, (N.at?.[0] ?? 0.15) * dur, (N.at?.[1] ?? 0.97) * dur, 0.5, 0.4);
  if (a <= 0) return;
  const u = H / 1080, s = 21 * u * (VERT ? 1.25 : 1);
  const maxW = VERT ? W * 0.84 : W * 0.34;
  font(ctx, s, 400);
  const words = N.text.split(' '); const lines = []; let cur = '';
  for (const w of words) { const tst = cur ? cur + ' ' + w : w; if (ctx.measureText(tst).width > maxW) { lines.push(cur); cur = w; } else cur = tst; }
  lines.push(cur);
  const x = VERT ? W * 0.08 : W * 0.045, y = VERT ? H * 0.075 : H * 0.075;
  ctx.save(); ctx.globalAlpha = a * 0.95;
  ctx.fillStyle = 'rgba(8,10,14,0.42)';
  const bh = (lines.length + 1) * s * 1.38 + 14 * u;
  ctx.fillRect(x - 16 * u, y - 14 * u, maxW + 32 * u, bh);
  ctx.fillStyle = ACCENT; ctx.fillRect(x - 16 * u, y - 14 * u, 2.5 * u, bh);
  font(ctx, s * 0.78, 700); ctx.letterSpacing = `${3 * u}px`; ctx.fillStyle = ACCENT;
  ctx.fillText((N.label ?? 'Scientific context').toUpperCase(), x, y + s * 0.75);
  font(ctx, s, 400); ctx.letterSpacing = '0px'; ctx.fillStyle = 'rgba(232,238,242,0.95)';
  lines.forEach((l, i) => ctx.fillText(l, x, y + s * 0.75 + (i + 1) * s * 1.38));
  ctx.restore();
}

function timer(ctx, T, t, W, H, VERT) {
  const a = smooth(T.show[0], T.show[0] + 0.4, t) * (1 - smooth(T.show[1] - 0.4, T.show[1], t));
  if (a <= 0) return;
  const u = H / 1080;
  const el = clamp((t - T.start) / (T.end - T.start));
  const secs = Math.min(T.count, Math.floor(el * T.count + 1e-6));
  const cx = VERT ? W * 0.5 : W * 0.86, cy = VERT ? H * 0.68 : H * 0.24, r = 74 * u;
  ctx.save(); ctx.globalAlpha = a;
  ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 3 * u; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = WARM; ctx.lineWidth = 4 * u; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * el); ctx.stroke();
  for (let i = 0; i < T.count; i++) { const an = -Math.PI / 2 + i / T.count * Math.PI * 2; ctx.fillStyle = i < secs ? WARM : 'rgba(255,255,255,0.35)';
    ctx.beginPath(); ctx.arc(cx + Math.cos(an) * (r + 14 * u), cy + Math.sin(an) * (r + 14 * u), 2.6 * u, 0, Math.PI * 2); ctx.fill(); }
  ctx.textAlign = 'center'; font(ctx, 58 * u, 300); ctx.fillStyle = WHITE + '0.97)';
  ctx.fillText(el >= 1 ? T.count : secs, cx, cy + 18 * u);
  font(ctx, 15 * u, 600); ctx.letterSpacing = `${3 * u}px`; ctx.fillStyle = 'rgba(220,230,235,0.8)';
  ctx.fillText(T.label.toUpperCase(), cx, cy + r + 46 * u);
  ctx.restore();
}

function chapter(ctx, shot, lt, W, H, VERT, meta) {
  const C = shot.chapter; if (!C) return;
  const a = fade(lt, 0.2, 4.2, 0.5, 0.6); if (a <= 0) return;
  const u = H / 1080;
  const x = VERT ? W * 0.08 : W * 0.045, y = VERT ? H * 0.06 : H * 0.085;
  if (shot.note) return; // notes occupy the corner
  ctx.save(); ctx.globalAlpha = a * 0.9;
  font(ctx, 18 * u, 700); ctx.letterSpacing = `${4 * u}px`; ctx.fillStyle = ACCENT;
  ctx.fillText(String(C.n).padStart(2, '0'), x, y);
  const k = ease.out(clamp((lt - 0.2) / 0.8));
  ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.fillRect(x + 40 * u, y - 6 * u, 46 * u * k, 1.5 * u);
  font(ctx, 18 * u, 500); ctx.fillStyle = 'rgba(240,244,246,0.92)'; ctx.fillText(C.text.toUpperCase(), x + 100 * u, y);
  ctx.restore();
}

export function drawOverlay(ctx, { W, H, VERT, t, shot, cam, globalFade, meta, anchors }) {
  ctx.clearRect(0, 0, W, H);
  const lt = t - shot.start, dur = shot.end - shot.start;
  ctx.save(); ctx.globalAlpha = 1; ctx.textBaseline = 'alphabetic';
  if (shot.conceptual !== false) {
    const u = H / 1080; font(ctx, 13 * u * (VERT ? 1.25 : 1), 600); ctx.letterSpacing = `${2.5 * u}px`;
    ctx.fillStyle = 'rgba(220,228,232,0.42)'; ctx.textAlign = 'right';
    ctx.fillText(shot.badge ?? 'CONCEPTUAL VISUALIZATION · NOT TO SCALE', W - (VERT ? W * 0.06 : W * 0.035), VERT ? H * 0.04 : H * 0.06);
    ctx.textAlign = 'left';
  }
  chapter(ctx, shot, lt, W, H, VERT, meta);
  for (const L of shot.labels || []) callout(ctx, L, shot, cam, lt, dur, W, H, VERT, anchors);
  if (shot.title) title(ctx, shot.title, lt, dur, W, H, VERT);
  if (shot.note) note(ctx, shot.note, lt, dur, W, H, VERT);
  if (shot.timer) timer(ctx, shot.timer, t, W, H, VERT);
  ctx.restore();
  if (globalFade < 1) { ctx.globalCompositeOperation = 'destination-in'; ctx.fillStyle = `rgba(0,0,0,${globalFade})`; ctx.fillRect(0, 0, W, H); ctx.globalCompositeOperation = 'source-over'; }
}
