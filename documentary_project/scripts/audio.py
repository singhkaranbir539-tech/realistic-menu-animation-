"""Sound design + mix. Everything is synthesised here (no third-party audio).

  audio/narration_processed.wav  narration: HPF, light denoise, de-ess, presence EQ, compression
  audio/music.wav                original procedural score (D minor, cinematic pads/pulse/arp)
  audio/sfx.wav                  impacts, whooshes, ticks, pulses, textures from storyboard cues
  audio/final_mix.wav            ducked mix, loudness-normalised to -14 LUFS / -1.5 dBTP
  audio/mix_report.json
"""
import json, os, subprocess
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, sosfiltfilt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SR = 48000
shots = json.load(open(f"{ROOT}/storyboard/shots.json"))
DUR = shots["duration"]; N = int(DUR * SR)
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR

def run(cmd): subprocess.run(cmd, check=True)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def env_ad(n, a, d): e = np.ones(n); na = max(1, int(a * SR)); e[:na] = np.linspace(0, 1, na); e[na:] = np.exp(-np.arange(n - na) / (d * SR)); return e
def place(buf, x, t, gain=1.0, pan=0.0):
    i = int(t * SR); x = x[: max(0, len(buf[0]) - i)]
    if i < 0 or len(x) == 0: return
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[0, i:i + len(x)] += x * gain * l * 1.414; buf[1, i:i + len(x)] += x * gain * r * 1.414
def midi(n): return 440 * 2 ** ((n - 69) / 12)

# ------------------------------------------------------------ narration
run(["ffmpeg", "-y", "-v", "error", "-i", f"{ROOT}/audio/narration_raw.wav", "-af",
     "highpass=f=70,afftdn=nr=6:nf=-50,deesser=i=0.35:m=0.5:f=0.5,equalizer=f=180:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2,"
     "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,alimiter=limit=0.89",
     "-ar", str(SR), "-ac", "1", f"{ROOT}/audio/narration_processed.wav"])
nar, _ = sf.read(f"{ROOT}/audio/narration_processed.wav"); nar = np.pad(nar, (0, max(0, N - len(nar))))[:N]
# speech envelope for ducking (smoothed RMS)
rms = np.sqrt(np.convolve(nar ** 2, np.ones(2400) / 2400, 'same'))
speech = (rms > 0.01).astype(float)
speech = np.convolve(speech, np.ones(int(0.25 * SR)) / int(0.25 * SR), 'same')

# ------------------------------------------------------------ score
# section chords (MIDI roots / chord tones), D minor palette
SECT = [(0, 17, [50, 57, 62, 65]), (17, 34, [46, 53, 58, 62]), (34, 51, [53, 60, 65, 69]), (51, 68, [48, 55, 60, 64]),
        (68, 85, [50, 57, 62, 65]), (85, 102, [43, 50, 55, 58]), (102, 119, [45, 52, 57, 61]), (119, 136, [50, 57, 62, 65]),
        (136, 155, [46, 53, 58, 62]), (155, DUR, [50, 57, 62, 69])]
music = np.zeros((2, N))
def pad_voice(freq, n, det=0.0):
    tt = np.arange(n) / SR; ph = 2 * np.pi * freq * (1 + det) * tt
    x = np.sin(ph) * 0.6 + 0.25 * np.sin(2 * ph + 0.3) + 0.12 * np.sin(3 * ph + 1.1) + 0.05 * np.sin(5 * ph)
    return x * (1 + 0.15 * np.sin(2 * np.pi * 0.13 * tt + det * 400))
for s0, s1, ch in SECT:
    n = int((s1 - s0 + 2.5) * SR)
    e = np.minimum(1, np.arange(n) / (2.0 * SR)) * np.minimum(1, (n - np.arange(n)) / (2.5 * SR))
    for k, m in enumerate(ch):
        for side, det in ((0, -0.0025), (1, 0.0025)):
            v = pad_voice(midi(m), n, det + k * 0.0004) * e * (0.05 if k else 0.065)
            place(music, lp(v, 1800), s0 - 1.2, 1.0, -0.6 if side == 0 else 0.6)
    # sub drone on the root
    sub = np.sin(2 * np.pi * midi(ch[0] - 12) * np.arange(n) / SR) * e * 0.05
    place(music, sub, s0 - 1.2)
# soft plucked arpeggio (sections 2-4, 9) and tension pulse (5, 7, 8)
def pluck(f, d=0.9):
    n = int(d * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 5) * np.minimum(1, tt / 0.004)
bpm = 84; eighth = 60 / bpm / 2
for si in (1, 2, 3, 8):
    s0, s1, ch = SECT[si]; tt = s0 + 1.0; k = 0
    seq = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12, ch[1] + 24, ch[3] + 12]
    while tt < s1 - 1.0:
        place(music, lp(pluck(midi(seq[k % len(seq)])), 3500), tt, 0.035, -0.4 + 0.8 * ((k * 0.37) % 1)); tt += eighth; k += 1
def thump(f0=55, d=0.6):
    n = int(d * SR); tt = np.arange(n) / SR; f = f0 * (1 + 1.5 * np.exp(-tt * 30))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7)
for si in (0, 4, 6, 7):
    s0, s1, ch = SECT[si]; tt = s0 + (5.0 if si == 0 else 0.6)
    while tt < s1 - 0.6: place(music, thump(midi(ch[0] - 12)), tt, 0.09); tt += 60 / bpm
# rising swell into each section
for s0, _, _ in SECT[1:]:
    n = int(2.2 * SR); tt = np.arange(n) / SR
    sw = hp(rng.standard_normal(n), 400) * (tt / tt[-1]) ** 3 * 0.04
    place(music, bp(sw, 500, 6000), s0 - 2.2, 1.0)

# ------------------------------------------------------------ SFX library
def noise(n): return rng.standard_normal(n)
def impact(d=2.5, f0=48):
    n = int(d * SR); tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 2.5 * np.exp(-tt * 18))) / SR) * np.exp(-tt * 1.8)
    click = lp(noise(n), 3000) * np.exp(-tt * 60) * 0.5
    tail = lp(noise(n), 300) * np.exp(-tt * 1.2) * 0.25
    return body + click + tail
def whoosh(d=1.0, lo=300, hi=4000, rise=True):
    n = int(d * SR); x = noise(n); out = np.zeros(n); seg = 2048
    for i in range(0, n, seg):
        u = i / n; f = lo * (hi / lo) ** (u if rise else 1 - u); f = min(f, SR / 2.2)
        out[i:i + seg] = bp(x[i:i + seg], f * 0.7, min(f * 1.4, SR / 2.1), 1)[: len(out[i:i + seg])]
    e = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    return lp(out, 9000) * e
def tick():
    n = int(0.12 * SR); tt = np.arange(n) / SR
    return (bp(noise(n), 2500, 6000) * np.exp(-tt * 120) * 0.8 + np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt * 90) * 0.3)
def chime(f=880, d=2.5):
    n = int(d * SR); tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * k * tt) * np.exp(-tt * (1.5 + k)) / k for k in (1, 2.76, 5.4)) * np.minimum(1, tt / 0.003)
def shimmer(d=2.0):
    n = int(d * SR); tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * tt + rng.random() * 6) for f in (2093, 2637, 3136, 3951)) * np.sin(np.pi * tt / d) ** 2 * 0.15 + hp(noise(n), 6000) * np.sin(np.pi * tt / d) ** 2 * 0.05
def granular(d=2.0, dens=300):
    n = int(d * SR); x = np.zeros(n)
    for i in rng.integers(0, n - 200, int(dens * d)): x[i:i + 60] += noise(60) * np.hanning(60) * rng.random()
    return bp(x, 1500, 9000) * np.sin(np.pi * np.arange(n) / n)
def fluid(d=3.0):
    n = int(d * SR); tt = np.arange(n) / SR
    return lp(noise(n), 250) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * tt)) * np.sin(np.pi * tt / d) * 2.0
def pulse_train(d=2.0, rate=3):
    n = int(d * SR); x = np.zeros(n)
    for k in range(int(d * rate)): s = thump(70, 0.3) * 0.6; i = int(k / rate * SR); x[i:i + len(s)] += s[: n - i]
    return x
def heartbeat(d=3.0):
    n = int(d * SR); x = np.zeros(n)
    for b in np.arange(0.2, d - 0.4, 0.9):
        for o, g in ((0, 1), (0.22, 0.7)): s = thump(45, 0.35) * g; i = int((b + o) * SR); x[i:i + len(s)] += s[: n - i]
    return x
def drone(d=4.0, f=73.4):
    n = int(d * SR); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.5 * tt * 1.003)) * np.sin(np.pi * tt / d) ** 2 * 0.5

sfx = np.zeros((2, N)); cues = []
def cue(kind, t, gain, x, pan=0.0): place(sfx, x, t, gain, pan); cues.append({"t": round(t, 3), "sfx": kind, "gain": gain})
cue("hook impact", 0.12, 0.55, impact(3.0, 42))
cue("sub swell", 0.0, 0.35, drone(2.0, 36.7))
for s in shots["shots"]:
    t0, t1, d = s["start"], s["end"], s["end"] - s["start"]
    tr = s.get("trans", {}).get("type", "cut")
    if tr == "push": cue("push whoosh", t0 - 0.55, 0.3, whoosh(0.9, 200, 5000), 0.2)
    elif tr == "dissolve" and t0 > 1: cue("soft whoosh", t0 - 0.5, 0.12, whoosh(1.1, 150, 1500, False), -0.2)
    elif t0 > 1: cue("cut tick", t0 - 0.02, 0.06, tick())
    for sd in s.get("sound", []):
        k = sd.lower()
        if "title hit" in k or "final hit" in k: cue("title impact", t0 + (s.get("title", {}).get("at", [0.3])[0]), 0.4, impact(3.5, 40))
        elif "whoosh rising" in k: cue("rising whoosh", t0, 0.3, whoosh(d, 200, 6000))
        elif "impact" in k and "hook" not in k: cue("impact", t0 + 0.1, 0.3, impact(2.0, 55))
        elif "tick" in k and s.get("timer"):
            T = s["timer"]
            for i in range(T["count"] + 1): cue("timer tick", T["start"] + i * (T["end"] - T["start"]) / T["count"], 0.22, tick(), 0.3)
        elif "mechanical ticks" in k or "clicking" in k:
            for j in np.arange(t0 + 0.1, t1 - 0.1, 0.18): cue("micro click", j, 0.05, tick(), float(rng.uniform(-.6, .6)))
        elif "pulse" in k: cue("pulses", t0 + 0.1, 0.18, pulse_train(min(d - 0.2, 4), 2.5))
        elif "chime" in k or "tone" in k: cue("chime", t0 + 0.25, 0.08, chime(float(rng.choice([660, 784, 880, 988]))), float(rng.uniform(-.4, .4)))
        elif "shimmer" in k or "glassy" in k or "crystalline" in k: cue("shimmer", t0 + 0.1, 0.25, shimmer(min(d, 3)))
        elif "granular" in k or "powder" in k or "rustle" in k: cue("granular", t0, 0.22, granular(min(d, 4)))
        elif "fluid" in k: cue("fluid", t0, 0.35, fluid(d))
        elif "heartbeat" in k: cue("heartbeat", t0 + 0.3, 0.3, heartbeat(min(d - 0.3, 4)))
        elif "swell" in k: cue("swell", t0, 0.15, whoosh(min(d, 3), 100, 2000))
        elif "drone" in k or "tension" in k: cue("drone", t0, 0.25, drone(d, 55))
        elif "stretch" in k or "creak" in k: cue("stretch", t0 + 0.2, 0.12, bp(noise(int(min(d, 3) * SR)), 200, 900) * np.sin(np.linspace(0, np.pi, int(min(d, 3) * SR))))
        elif "bubbles" in k or "texture" in k or "ambience" in k or "drift" in k: cue("micro texture", t0, 0.12, granular(min(d, 3), 120))
        elif "rep pulses" in k or "low pulse" in k: cue("rep pulses", t0, 0.15, pulse_train(min(d, 4), 1.2))
# microscopic ambience bed per world
for s in shots["shots"]:
    if s["world"] in ("blood", "cell", "synthesis", "sarcomere", "fibers"):
        d = s["end"] - s["start"]; n = int(d * SR)
        bed = lp(noise(n), 400 if s["world"] == "blood" else 900) * 0.25 * np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (0.3 * SR))
        place(sfx, bed, s["start"], 0.12, 0)

# ------------------------------------------------------------ mix
duck = 1 - 0.55 * np.clip(speech, 0, 1)                 # about -7 dB under narration
fade = np.minimum(1, t_all / 0.6) * np.minimum(1, (DUR - t_all) / 2.0)
music *= duck * fade; sfx *= (1 - 0.3 * np.clip(speech, 0, 1)) * fade
music = np.stack([lp(music[0], 12000), lp(music[1], 12000)])
sf.write(f"{ROOT}/audio/music.wav", (music / max(1e-9, np.abs(music).max()) * 0.8).T.astype(np.float32), SR)
sf.write(f"{ROOT}/audio/sfx.wav", (sfx / max(1e-9, np.abs(sfx).max()) * 0.8).T.astype(np.float32), SR)
mix = np.stack([nar, nar]) * 1.0 + music * 1.0 + sfx * 1.0
sf.write(f"{ROOT}/audio/premaster.wav", (mix / np.abs(mix).max() * 0.7).T.astype(np.float32), SR)
# two-pass loudness normalisation
p = subprocess.run(["ffmpeg", "-v", "info", "-i", f"{ROOT}/audio/premaster.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
js = json.loads(p[p.rindex("{"):p.rindex("}") + 1])
run(["ffmpeg", "-y", "-v", "error", "-i", f"{ROOT}/audio/premaster.wav", "-af",
     f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true",
     "-ar", str(SR), "-c:a", "pcm_s24le", f"{ROOT}/audio/final_mix.wav"])
os.remove(f"{ROOT}/audio/premaster.wav")
p = subprocess.run(["ffmpeg", "-v", "info", "-i", f"{ROOT}/audio/final_mix.wav", "-af", "loudnorm=I=-14:TP=-1.5:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(p[p.rindex("{"):p.rindex("}") + 1])
rep = {"integrated_lufs": float(m["input_i"]), "true_peak_dbtp": float(m["input_tp"]), "lra": float(m["input_lra"]), "duration_s": DUR,
       "music_duck_db_under_speech": round(20 * np.log10(0.45), 1), "sfx_cues": len(cues), "cues": cues}
json.dump(rep, open(f"{ROOT}/audio/mix_report.json", "w"), indent=1)
print({k: v for k, v in rep.items() if k != "cues"})
