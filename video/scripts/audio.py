"""Synthesise the cinematic electronic score and sound effects, then mix with the
narration. Music is ducked under speech (sidechain from the narration envelope).
Writes output/narration.wav, build/music.wav, build/sfx.wav, build/mix.wav."""
import json, sys, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

ROOT = sys.path[0] + "/.."
SR, TOTAL = 48000, 172
N = SR * TOTAL
t = np.arange(N) / SR
rng = np.random.default_rng(1)
scenes = json.load(open(f"{ROOT}/scenes.json"))

def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)
def env_adsr(n, a, r):
    e = np.ones(n); ai = int(a * SR); ri = int(r * SR)
    e[:ai] = np.linspace(0, 1, ai); e[-ri:] *= np.linspace(1, 0, ri); return e
def place(buf, sig, at, gain=1.0):
    i = int(at * SR); j = min(len(buf), i + len(sig))
    if i < len(buf): buf[i:j] += sig[: j - i] * gain

# ---------------- music ----------------
BPM = 100; beat = 60 / BPM
# chord roots per 4 bars (minor, cinematic): Am - F - C - G  (Hz of root)
prog = [55.0, 43.65, 65.41, 49.0]
chords = {55.0: [0, 3, 7, 10], 43.65: [0, 4, 7, 11], 65.41: [0, 4, 7, 9], 49.0: [0, 4, 7, 10]}
bar = 4 * beat
music = np.zeros(N); pad = np.zeros(N); bass = np.zeros(N); arp = np.zeros(N); drums = np.zeros(N)
# section intensity: low at intro/outro, fuller mid
def intensity(x):
    return np.interp(x, [0, 8, 17, 60, 68, 120, 136, 150, 160, 168, 172], [0.25, 0.45, 0.7, 0.75, 0.9, 0.9, 1.0, 1.0, 0.7, 0.4, 0.0])
nb = int(TOTAL / bar) + 1
for b in range(nb):
    t0 = b * bar; root = prog[(b // 2) % 4]; iv = chords[root]
    n = int(bar * SR); tt = np.arange(n) / SR
    # pad: detuned saws, low-passed
    p = np.zeros(n)
    for k in iv:
        f = root * 4 * 2 ** (k / 12)
        for d in (-0.12, 0.0, 0.11):
            p += ((tt * f * (1 + d / 100) * 1.0) % 1.0 - 0.5)
    p = lp(p, 1400) * env_adsr(n, 0.6, 0.6) * 0.05
    place(pad, p, t0)
    # bass: pulsing 8ths
    for e in range(8):
        m = int(beat / 2 * SR); te = np.arange(m) / SR
        s = np.sin(2 * np.pi * root * 2 * te) + 0.3 * np.sin(2 * np.pi * root * 4 * te)
        place(bass, s * np.exp(-te * 7) * 0.22, t0 + e * beat / 2)
    # arpeggio 16ths (sine pluck)
    for e in range(16):
        m = int(beat / 4 * SR * 1.6); te = np.arange(m) / SR
        f = root * 8 * 2 ** (iv[(e * 3) % 4] / 12) * (2 if e % 8 == 7 else 1)
        s = (np.sin(2 * np.pi * f * te) + 0.25 * np.sin(2 * np.pi * f * 2 * te)) * np.exp(-te * 14)
        place(arp, s * 0.05, t0 + e * beat / 4)
    # drums: kick on 1 & 3, snare-ish clap on 2 & 4, hats
    for e in range(4):
        m = int(0.45 * SR); te = np.arange(m) / SR
        if e in (0, 2):
            kick = np.sin(2 * np.pi * (45 * te + 90 * (1 - np.exp(-te * 30)) / 30)) * np.exp(-te * 9)
            place(drums, kick * 0.55, t0 + e * beat)
        else:
            cl = bp(rng.standard_normal(m), 900, 3500) * np.exp(-te * 22)
            place(drums, cl * 0.18, t0 + e * beat)
        for h in range(2):
            hm = int(0.06 * SR); hh = hp(rng.standard_normal(hm), 7000) * np.exp(-np.arange(hm) / SR * 70)
            place(drums, hh * 0.05, t0 + e * beat + h * beat / 2)
I = intensity(t)
music = pad * (0.6 + 0.4 * I) + bass * I + arp * np.clip(I * 1.3 - 0.3, 0, 1) + drums * np.clip(I * 1.5 - 0.6, 0, 1)
# intro sub drone & outro swell
music += np.sin(2 * np.pi * 36.7 * t) * 0.12 * np.clip(1 - t / 10, 0, 1)
music *= np.clip((TOTAL - t) / 4.0, 0, 1)  # fade out over final 4 s

# ---------------- sfx ----------------
sfx = np.zeros(N)
def impact():
    m = int(2.5 * SR); te = np.arange(m) / SR
    boom = np.sin(2 * np.pi * (30 * te + 60 * (1 - np.exp(-te * 6)) / 6)) * np.exp(-te * 2.2)
    noise = lp(rng.standard_normal(m), 400) * np.exp(-te * 5) * 0.6
    return (boom + noise) * 0.6
def whoosh(d=0.7, up=True):
    m = int(d * SR); te = np.arange(m) / SR; x = rng.standard_normal(m)
    out = np.zeros(m); seg = m // 12
    for k in range(12):  # sweep band-pass
        f = 300 * (12 if up else 1) ** (k / 11) if up else 3600 / (12 ** (k / 11))
        part = bp(x, max(80, f * 0.6), min(SR / 2 - 100, f * 1.6))
        w = np.zeros(m); w[k * seg:(k + 1) * seg + seg] = 1; out += part * w[:m]
    return lp(out, 6000) * np.sin(np.pi * te / d) ** 2 * 0.35
def zap():
    m = int(0.35 * SR); te = np.arange(m) / SR
    f = 1800 * np.exp(-te * 9) + 200
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-te * 12)
    return hp(lp(s, 5000), 300) * 0.08
def blip():
    m = int(0.12 * SR); te = np.arange(m) / SR
    return (np.sin(2 * np.pi * 1760 * te) + 0.5 * np.sin(2 * np.pi * 2640 * te)) * np.exp(-te * 40) * 0.06
def stretch_sfx(d=2.5):
    m = int(d * SR); te = np.arange(m) / SR
    creak = bp(rng.standard_normal(m), 120, 700) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * te))
    return creak * np.sin(np.pi * te / d) * 0.25

trans_at = {"flash": "zap", "whip": "whoosh", "depth": "whoosh", "black": None}
tin = {1: "black", 2: "flash", 3: "whip", 4: "depth", 5: "flash", 6: "whip", 7: "depth", 8: "flash", 9: "whip", 10: "flash"}
for sc in scenes:
    s0 = sc["start"]
    place(sfx, impact(), s0 + (1.0 if sc["id"] == 1 else 0.02), 0.7 if sc["id"] > 1 else 0.9)
    if sc["id"] > 1:
        k = tin[sc["id"]]
        if k == "flash": place(sfx, zap(), s0 - 0.05); place(sfx, zap(), s0 + 0.1, 0.6)
        else: place(sfx, whoosh(0.8), s0 - 0.5)
    place(sfx, blip(), s0 + 0.6); place(sfx, blip(), s0 + 0.75, 0.7)  # title HUD
    for k in range(3): place(sfx, blip(), s0 + 4 + k * 3.7, 0.6)       # HUD tags
# neural pulses through the intro + mascot appearance
for k in range(10): place(sfx, zap(), 0.4 + k * 0.6, 0.5 + 0.05 * k)
place(sfx, whoosh(1.2), 5.8)
# eccentric scenes: muscle stretching textures and subtle mechanical impacts
for at in (69.0, 73.1, 77.2): place(sfx, stretch_sfx(3.0), at)
for at in (104.0, 107.0): place(sfx, stretch_sfx(3.2), at)
for k in range(9): place(sfx, blip(), 103.8 + k, 1.2)                # 8-second timer ticks
for at in (124.9, 126.6, 128.3, 130.0): place(sfx, whoosh(0.5), at, 0.6)  # dashboard moves
place(sfx, impact(), 168.3, 0.9)  # final title hit
sfx *= np.clip((TOTAL - t) / 1.2, 0, 1)

# ---------------- narration & mix ----------------
nar, nsr = sf.read(f"{ROOT}/build/narration.wav")
nar = resample_poly(nar, SR, nsr)[:N]; nar = np.pad(nar, (0, N - len(nar)))
# speech-driven ducking for music
win = int(0.05 * SR)
def movavg(x, w):
    c = np.cumsum(np.pad(x, (w // 2, w - w // 2)))
    return (c[w:] - c[:-w])[: len(x)] / w
e = np.sqrt(np.maximum(movavg(nar ** 2, win), 0))
e = (e > 0.01).astype(float)
e = movavg(e, int(0.4 * SR))
duck = 1 - 0.55 * np.clip(e, 0, 1)
music_n = music / np.max(np.abs(music)); sfx_n = sfx / np.max(np.abs(sfx))
mix = nar * 1.0 + music_n * 0.32 * duck + sfx_n * 0.42 * (1 - 0.3 * np.clip(e, 0, 1))
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
mix = mix / np.max(np.abs(mix)) * 0.95
sf.write(f"{ROOT}/build/music.wav", music_n * 0.8, SR)
sf.write(f"{ROOT}/build/sfx.wav", sfx_n * 0.8, SR)
sf.write(f"{ROOT}/output/narration.wav", nar / np.max(np.abs(nar)) * 0.95, SR)
sf.write(f"{ROOT}/build/mix.wav", np.stack([mix, mix], 1), SR)
print("ok", mix.shape)
