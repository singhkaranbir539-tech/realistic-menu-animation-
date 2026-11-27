"""Original score + sound design + final mix, all synthesised from scratch (no samples, no licensed audio).

Outputs (48 kHz, 24-bit stereo):
  audio/music/score.wav, audio/sound_effects/sfx.wav, audio/final_mix.wav
Mix targets: music ~18 dB below narration (RMS while speaking), extra ducking under speech,
integrated loudness -14 LUFS, true peak <= -1 dBTP.
"""
import os, json, numpy as np, soundfile as sf
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000; T = 30.0; N = int(SR * T)
t = np.arange(N) / SR
rng = np.random.default_rng(2024)


def env_adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    sus = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, a, False), np.linspace(1, s, d, False), np.full(sus, s), np.linspace(s, 0, r)])
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def place(buf, x, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    m = min(len(x), len(buf) - i)
    buf[i:i + m] += x[:m]


def lp(x, fc, order=2):
    b, a = signal.butter(order, min(fc, SR / 2 - 100) / (SR / 2)); return signal.lfilter(b, a, x, axis=0)


def hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), "high"); return signal.lfilter(b, a, x, axis=0)


def bp(x, f1, f2, order=2):
    b, a = signal.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band"); return signal.lfilter(b, a, x, axis=0)


def tv_lowpass(x, fc_curve):
    """Time-varying one-pole-pair lowpass (cutoff per sample)."""
    y = np.zeros_like(x); s1 = 0.0; s2 = 0.0
    g = 1 - np.exp(-2 * np.pi * np.asarray(fc_curve) / SR)
    for i in range(len(x)):
        s1 += g[i] * (x[i] - s1); s2 += g[i] * (s1 - s2); y[i] = s2
    return y


def stereo_reverb(x, decay=3.2, mix=0.35, seed=1):
    r = np.random.default_rng(seed)
    n = int(decay * SR)
    tt = np.arange(n) / SR
    irs = []
    for ch in range(2):
        ir = r.standard_normal(n) * np.exp(-tt * 6.9 / decay)
        ir = lp(ir, 6000); ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
        irs.append(ir / np.sqrt((ir ** 2).sum()))
    mono = x if x.ndim == 1 else x.mean(1)
    wet = np.stack([signal.fftconvolve(mono, irs[c])[: len(mono)] for c in range(2)], 1)
    dry = np.stack([x, x], 1) if x.ndim == 1 else x
    return dry * (1 - mix) + wet * mix * 1.6


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# =============================================================== MUSIC
music = np.zeros((N, 2))

# --- 1. atmospheric pad: detuned saws, slow filter, chord progression (D minor, original voicing)
chords = [  # (start, end, midi notes)
    (0.0, 5.2, [38, 50, 57, 62, 64]),         # Dm(add9)
    (5.0, 11.2, [34, 50, 57, 62, 65, 69]),     # Bbmaj7 / build
    (11.0, 17.2, [43, 50, 58, 62, 65, 69]),    # Gm9 - discovery
    (17.0, 23.2, [41, 53, 57, 60, 65, 72]),    # F(add9) - emotional rise
    (23.0, 30.0, [38, 50, 57, 62, 65, 69, 74]),  # Dm resolve
]
pad = np.zeros((N, 2))
for c0, c1, notes in chords:
    n = int((c1 - c0 + 1.6) * SR); tt = np.arange(n) / SR
    e = env_adsr(n, 1.4, 0.5, 0.85, 1.6)
    seg = np.zeros((n, 2))
    for m in notes:
        f = note(m)
        for ch, det in enumerate((-0.07, 0.07)):
            for d in (-1, 0, 1):
                ff = f * 2 ** ((det + d * 0.05) / 12)
                ph = rng.uniform(0, 1)
                saw = 2 * ((tt * ff + ph) % 1) - 1
                seg[:, ch] += saw * (0.5 if d else 0.8) / (1 + (m > 60) * 0.6)
    seg *= e[:, None]
    i = int(c0 * SR); m_ = min(n, N - i)
    pad[i:i + m_] += seg[:m_]
# filter sweeps following the structure
fc = np.interp(t, [0, 5, 11, 17, 21, 23, 26, 30], [380, 520, 1300, 1100, 2300, 1700, 900, 300])
fc *= 1 + 0.15 * np.sin(2 * np.pi * t / 7.0)
for ch in range(2):
    pad[:, ch] = tv_lowpass(pad[:, ch], fc)
pad = hp(pad, 60)
music += pad * 0.05

# --- 2. soft strings (additive with vibrato, slow bow attack) entering at 11s, swelling 17-23
def string_voice(m, dur, vib=5.2, bright=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = note(m) * (1 + 0.004 * np.sin(2 * np.pi * vib * tt + rng.uniform(0, 6)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = sum((1 / k ** (1.2 / bright)) * np.sin(k * ph + rng.uniform(0, 6)) for k in range(1, 12))
    y *= 1 + 0.08 * rng.standard_normal(n).cumsum() / np.sqrt(np.arange(1, n + 1)) * 0
    return y * env_adsr(n, 1.8, 0.4, 0.9, 1.8)


strings = np.zeros((N, 2))
for (st, dur, ms, amp) in [(11.0, 6.5, [62, 69], 0.5), (17.0, 6.6, [65, 72, 77], 0.85), (23.0, 6.6, [62, 69, 74], 0.7)]:
    for j, m in enumerate(ms):
        v = string_voice(m, dur)
        pan = 0.3 + 0.4 * (j / max(1, len(ms) - 1))
        place(strings[:, 0], v * amp * (1 - pan), st); place(strings[:, 1], v * amp * pan, st)
strings = lp(strings, 4200)
strings *= np.interp(t, [0, 26.5, 29.6, 30], [1, 1, 0, 0])[:, None]
music += strings * 0.035

# --- 3. low-frequency pulses (heartbeat-like sub throb) 0-5 and 17-23, and a ticking build 5-11
sub = np.zeros(N)
def thump(f0=52, dur=0.35, amp=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = f0 * (1 + 0.6 * np.exp(-tt * 30)); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tt * 9) * amp
for tb in np.arange(0.4, 5.0, 0.97):
    place(sub, thump(48, amp=0.7), tb); place(sub, thump(44, amp=0.45), tb + 0.28)
for tb in np.arange(17.2, 23.0, 0.97):
    place(sub, thump(50, amp=0.55), tb); place(sub, thump(46, amp=0.35), tb + 0.28)
music += np.stack([sub, sub], 1) * 0.10
# building pulse 5-11: soft muted plucks on D, 8th notes, accelerating filter
pl = np.zeros(N)
bpm = 96; step = 60 / bpm / 2
for k_, tb in enumerate(np.arange(5.0, 11.0, step)):
    n = int(0.3 * SR); tt = np.arange(n) / SR
    m = [62, 69, 65, 69][k_ % 4]
    y = np.sign(np.sin(2 * np.pi * note(m) * tt)) * np.exp(-tt * 18)
    place(pl, lp(y, 900 + 200 * (tb - 5)) * (0.3 + 0.12 * (tb - 5)), tb)
plr = stereo_reverb(pl, 2.0, 0.5, seed=5)
music += plr * 0.012
# shimmer bells in discovery section 11-17 (FM-ish, sparse)
bells = np.zeros(N)
for tb, m in [(11.4, 81), (12.6, 86), (13.5, 84), (14.7, 88), (15.6, 86), (16.4, 93)]:
    n = int(2.5 * SR); tt = np.arange(n) / SR
    mod = np.sin(2 * np.pi * note(m) * 3.5 * tt) * 1.5 * np.exp(-tt * 3)
    place(bells, np.sin(2 * np.pi * note(m) * tt + mod) * np.exp(-tt * 2.2) * 0.25, tb)
music += stereo_reverb(bells, 3.5, 0.6, seed=7) * 0.012

# --- 4. cinematic percussion: soft toms at section changes, big hit at 23s
perc = np.zeros(N)
def tom(f0, amp, dur=1.2):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = f0 * (1 + 1.2 * np.exp(-tt * 18)); ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-tt * 4.5)
    nz = lp(rng.standard_normal(n), 1800) * np.exp(-tt * 25) * 0.4
    return (body + nz) * amp
for tb, amp in [(5.0, 0.35), (11.0, 0.45), (17.0, 0.5), (20.4, 0.3), (21.5, 0.35), (22.3, 0.4)]:
    place(perc, tom(70, amp), tb)
place(perc, tom(45, 1.0, 3.0) + 0, 23.0)
music += stereo_reverb(perc, 2.6, 0.35, seed=9) * 0.09

# master music envelope: fade in, final fade to silence
music *= np.interp(t, [0, 0.8, 28.0, 29.7, 30], [0.25, 1, 1, 0, 0])[:, None]
music = np.tanh(music * 1.2) / 1.2
music_rev = stereo_reverb(music.mean(1), 3.5, 1.0, seed=11) * 0.15
music = music + music_rev

# =============================================================== SOUND EFFECTS (timed to picture)
sfx = np.zeros((N, 2))

def pan(x, p):  # p in [-1,1]
    return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], 1)


def whoosh(dur, f1, f2, amp=1.0, p0=-0.6, p1=0.6):
    n = int(dur * SR); tt = np.arange(n) / SR
    x = rng.standard_normal(n)
    fc = np.geomspace(f1, f2, n)
    y = tv_lowpass(x, fc) - tv_lowpass(x, fc * 0.25)
    e = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
    y *= e * amp / (np.abs(y).max() + 1e-9)
    pp = np.linspace(p0, p1, n)
    return np.stack([y * np.sqrt((1 - pp) / 2), y * np.sqrt((1 + pp) / 2)], 1)


def impact(amp=1.0, f0=38, dur=3.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = f0 * (1 + 2.0 * np.exp(-tt * 12)); ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-tt * 1.6) + lp(rng.standard_normal(n), 400) * np.exp(-tt * 8) * 0.5
    return pan(y * amp, 0)


def heartbeat(t0, t1, amp, bpm=62, fade=None):
    out = np.zeros(N)
    per = 60 / bpm
    for tb in np.arange(t0, t1, per):
        a = amp * (np.interp(tb, fade[0], fade[1]) if fade else 1)
        for off, f0, aa in [(0, 55, 1.0), (0.27, 48, 0.7)]:
            n = int(0.25 * SR); tt = np.arange(n) / SR
            f = f0 * (1 + 0.8 * np.exp(-tt * 40)); ph = 2 * np.pi * np.cumsum(f) / SR
            y = np.sin(ph) * np.exp(-tt * 16) + lp(rng.standard_normal(n), 300) * np.exp(-tt * 60) * 0.3
            place(out, y * a * aa, tb + off)
    return pan(lp(out, 400), 0)


# scene 1: opening low impact, deep heartbeat, penetration whoosh, upward whoosh to the brain
place(sfx, impact(0.5, 34, 3.5), 0.0)
sfx += heartbeat(0.35, 5.0, 0.55)
place(sfx, whoosh(1.0, 300, 3500, 0.35, -0.5, 0.4), 1.45)
place(sfx, whoosh(0.8, 200, 5000, 0.25, 0.3, -0.3), 4.55)
place(sfx, impact(0.25, 42, 1.5), 2.0)

# scene 2: subtle electrical pulses + soft digital neural textures, deep drone
el = np.zeros(N)
for tb in np.sort(rng.uniform(5.3, 10.9, 34)):
    n = int(rng.uniform(0.02, 0.08) * SR); tt = np.arange(n) / SR
    zap = np.sin(2 * np.pi * rng.uniform(900, 2600) * tt * (1 + 2 * tt)) * np.exp(-tt * 70)
    crack = bp(rng.standard_normal(n), 2500, 9000) * np.exp(-tt * 120) * 0.6
    place(el, (zap * 0.5 + crack) * rng.uniform(0.25, 0.7), tb)
tex = np.zeros(N)
for tb in np.arange(5.2, 11.0, 0.11):
    n = int(0.06 * SR); tt = np.arange(n) / SR
    place(tex, np.sin(2 * np.pi * rng.choice([2093, 2349, 2637, 3136]) * tt) * np.exp(-tt * 60) * rng.uniform(0.05, 0.18), tb)
sfx += stereo_reverb(el + tex, 1.4, 0.4, seed=13) * 0.55
drone = np.sin(2 * np.pi * 36.7 * t) + 0.4 * np.sin(2 * np.pi * 55 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t))
sfx += pan(drone * np.interp(t, [4.8, 6.0, 10.6, 11.4], [0, 1, 1, 0]) * 0.05, 0)
place(sfx, whoosh(0.55, 800, 9000, 0.4, -0.2, 0.2), 10.55)      # neural impulse flash
place(sfx, impact(0.2, 60, 1.2), 10.95)

# scene 3: liquid movement, underwater ambience, rising sound into the vessel
uw = lp(rng.standard_normal(N), 260) * 2.5
uw *= (1 + 0.4 * np.sin(2 * np.pi * 0.31 * t)) * np.interp(t, [10.8, 11.6, 16.7, 17.4], [0, 1, 1, 0])
sfx += pan(uw, -0.1) * 0.10 + pan(np.roll(uw, 1200), 0.1) * 0.10
bub = np.zeros(N)
for tb in np.sort(rng.uniform(11.2, 16.8, 40)):
    n = int(0.05 * SR); tt = np.arange(n) / SR
    f0 = rng.uniform(300, 900)
    place(bub, np.sin(2 * np.pi * f0 * tt * (1 + 6 * tt)) * np.exp(-tt * 55) * rng.uniform(0.05, 0.18), tb)
sfx += stereo_reverb(bub, 1.0, 0.5, seed=17) * 0.5
rs = int(2.3 * SR); tt = np.arange(rs) / SR
riser = (tv_lowpass(rng.standard_normal(rs), np.geomspace(200, 7000, rs)) * 2 + 0.3 * np.sin(2 * np.pi * np.cumsum(np.geomspace(110, 440, rs)) / SR)) * (tt / tt[-1]) ** 2
place(sfx, pan(riser * 0.25, 0), 14.75)
place(sfx, whoosh(0.7, 250, 3000, 0.35, 0.5, -0.5), 16.6)

# scene 4: heartbeat rhythm, organic fluid movement, low impact, vessel->muscle whoosh
sfx += heartbeat(17.1, 23.0, 0.35, bpm=58)
fl = lp(rng.standard_normal(N), 500) * 1.8
pulse = 0.6 + 0.4 * np.clip(np.sin(2 * np.pi * (t - 17.1) / (60 / 58)), 0, 1) ** 3
fl *= pulse * np.interp(t, [16.9, 17.5, 22.6, 23.2], [0, 1, 1, 0])
sfx += pan(fl, 0) * 0.09
place(sfx, impact(0.3, 40, 2.0), 17.0)
place(sfx, whoosh(0.9, 200, 2500, 0.3, -0.4, 0.4), 19.6)

# scene 5: deep impact, heartbeat fading, atmosphere fading to silence
place(sfx, impact(0.75, 30, 4.5), 23.0)
sfx += heartbeat(23.6, 28.8, 0.4, bpm=56, fade=([23.6, 28.8], [1, 0.0]))
air = lp(rng.standard_normal(N), 1200) * np.interp(t, [22.8, 24, 28, 29.8], [0, 1, 0.6, 0]) * 0.8
sfx += pan(air, 0) * 0.03

sfx *= np.interp(t, [0, 29.5, 29.95, 30], [1, 1, 0, 0])[:, None]

# =============================================================== MIX
vo, sr = sf.read(os.path.join(ROOT, "audio/voiceover/narration_processed.wav"))
assert sr == SR
vo = vo[:N] if len(vo) >= N else np.pad(vo, (0, N - len(vo)))
timing = json.load(open(os.path.join(ROOT, "audio/voiceover/timing.json")))
speech = np.zeros(N, bool)
for ln in timing["lines"]:
    speech[int(ln["start"] * SR):int(ln["end"] * SR)] = True


def rms_db(x, m):
    x = x[m] if x.ndim == 1 else x[m].mean(1)
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)


vo_db = rms_db(vo, speech)
# sidechain duck envelope (extra 4 dB under speech, smooth)
duck = np.where(speech, 10 ** (-4 / 20), 1.0)
duck = signal.lfilter([1 - 0.9995], [1, -0.9995], duck)
mus_db = rms_db(music * duck[:, None], speech)
g_m = 10 ** ((vo_db - 18 - mus_db) / 20)
music_m = music * g_m * duck[:, None]
sfx_db = rms_db(sfx * duck[:, None], speech)
g_s = 10 ** ((vo_db - 19 - sfx_db) / 20)
sfx_m = sfx * g_s * np.where(speech, 0.85, 1.0)[:, None]
mix = np.stack([vo, vo], 1) + music_m + sfx_m
print(f"narration RMS {vo_db:.1f} dBFS | music while speaking {rms_db(music_m, speech):.1f} dBFS "
      f"({rms_db(music_m, speech)-vo_db:+.1f} dB rel) | sfx {rms_db(sfx_m, speech)-vo_db:+.1f} dB rel")

# loudness normalise to -14 LUFS then oversampled true-peak limiting at -1 dBTP
import pyloudnorm as pyln
meter = pyln.Meter(SR)
L = meter.integrated_loudness(mix)
mix *= 10 ** ((-14 - L) / 20)


def tp_limit(x, ceiling_db=-1.2, lookahead=0.005, release=0.08):
    up = signal.resample_poly(x, 4, 1, axis=0)
    pk = np.abs(up).max(1).reshape(-1, 4).max(1)[: len(x)]
    ceil = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    la = int(lookahead * SR)
    from scipy.ndimage import minimum_filter1d
    need = minimum_filter1d(np.pad(need, (0, la), constant_values=1), size=la + 1, origin=-(la // 2))[: len(x)]
    g = np.empty_like(need); cur = 1.0; rel = np.exp(-1 / (release * SR))
    for i in range(len(need)):
        cur = need[i] if need[i] < cur else rel * cur + (1 - rel) * need[i]; g[i] = cur
    return x * g[:, None]


mix = tp_limit(mix)
L2 = meter.integrated_loudness(mix)
tp = 20 * np.log10(np.abs(signal.resample_poly(mix, 4, 1, axis=0)).max())
print(f"final integrated loudness {L2:.2f} LUFS, true peak {tp:.2f} dBTP")
os.makedirs(os.path.join(ROOT, "audio/music"), exist_ok=True); os.makedirs(os.path.join(ROOT, "audio/sound_effects"), exist_ok=True)
sf.write(os.path.join(ROOT, "audio/music/score.wav"), (music / np.abs(music).max() * 0.7).astype(np.float32), SR, subtype="PCM_24")
sf.write(os.path.join(ROOT, "audio/sound_effects/sfx.wav"), (sfx / np.abs(sfx).max() * 0.7).astype(np.float32), SR, subtype="PCM_24")
sf.write(os.path.join(ROOT, "audio/final_mix.wav"), mix.astype(np.float32), SR, subtype="PCM_24")
json.dump({"narration_rms_dbfs": round(vo_db, 2), "music_rel_db": round(rms_db(music_m, speech) - vo_db, 2),
           "sfx_rel_db": round(rms_db(sfx_m, speech) - vo_db, 2), "lufs": round(L2, 2), "true_peak_dbtp": round(tp, 2)},
          open(os.path.join(ROOT, "audio/mix_report.json"), "w"), indent=1)
