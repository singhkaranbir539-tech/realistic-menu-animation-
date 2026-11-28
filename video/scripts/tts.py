"""Generate narration with Kokoro TTS (am_michael), one clause at a time so every
clause has an exact start/end time. Writes build/narration.wav, build/timing.json,
build/envelope.json (per-frame mouth-open amount for lip sync) and output/subtitles.srt."""
import json, re, sys, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
ROOT = sys.path[0] + "/.."
SR, FPS, TOTAL = 24000, 30, 172
k = Kokoro("/home/user/tts/kokoro.onnx", "/home/user/tts/voices.bin")
voice = k.get_voice_style("am_michael") * 0.7 + k.get_voice_style("am_onyx") * 0.3
scenes = json.load(open(f"{ROOT}/scenes.json"))
out = np.zeros(SR * TOTAL, dtype=np.float32)
timing = []
def pronounce(s):  # spoken form only; subtitles keep the written form
    return s.replace("MA30", "M A thirty").replace("Karbolyn", "Car-bo-lin")
for sc in scenes:
    clauses = [c.strip() for c in re.split(r"(?<=[.,])\s+", sc["text"]) if c.strip()]
    avail = sc["end"] - sc["start"] - 1.3
    speed, gapk = 0.96, 1.0
    for _ in range(4):
        pieces = []
        for c in clauses:
            a, _ = k.create(pronounce(c), voice=voice, speed=speed, lang="en-us")
            nz = np.where(np.abs(a) > 0.01)[0]
            a = a[max(0, nz[0] - 240): nz[-1] + 1200]
            gap = (0.42 if c.endswith(".") else 0.16) * gapk
            pieces.append((c, a, gap))
        total = sum(len(a) / SR + g for _, a, g in pieces) - pieces[-1][2]
        if total <= avail: break
        speed *= total / avail * 1.02; gapk *= 0.8
    print("scene", sc["id"], "speed", round(speed, 3))
    t = sc["start"] + 0.7 + max(0, (avail - total) * 0.35)
    for c, a, g in pieces:
        i = int(t * SR); out[i:i + len(a)] += a
        timing.append({"scene": sc["id"], "text": c, "start": round(t, 3), "end": round(t + len(a) / SR, 3)})
        t += len(a) / SR + g
    print("scene", sc["id"], "speech", round(total, 2), "of", sc["end"] - sc["start"])
out = out / np.max(np.abs(out)) * 0.89
sf.write(f"{ROOT}/build/narration.wav", out, SR)
json.dump(timing, open(f"{ROOT}/build/timing.json", "w"), indent=1)
# lip-sync envelope: RMS per video frame, smoothed, normalised 0..1
hop = SR // FPS
rms = np.array([np.sqrt(np.mean(out[i * hop:(i + 1) * hop] ** 2)) for i in range(TOTAL * FPS)])
rms = np.convolve(rms, [0.25, 0.5, 0.25], "same")
env = np.clip(rms / np.percentile(rms[rms > 0.01], 90), 0, 1.0)
json.dump([round(float(x), 3) for x in env], open(f"{ROOT}/build/envelope.json", "w"))
# subtitles: split clauses into <=5-word cards, time by character share
def ts(x):
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h:02}:{m:02}:{s:06.3f}".replace(".", ",")
cards = []
for c in timing:
    words = c["text"].split()
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 5 or (len(cur) >= 3 and len(" ".join(cur)) > 26):
            groups.append(cur); cur = []
    if cur:
        if groups and len(cur) <= 1: groups[-1] += cur
        else: groups.append(cur)
    chars = sum(len(" ".join(g)) for g in groups); t = c["start"]; dur = c["end"] - c["start"]
    for g in groups:
        d = dur * len(" ".join(g)) / chars
        cards.append({"scene": c["scene"], "text": " ".join(g), "start": round(t, 3), "end": round(t + d, 3)}); t += d
json.dump(cards, open(f"{ROOT}/build/captions.json", "w"), indent=1)
with open(f"{ROOT}/output/subtitles.srt", "w") as f:
    for i, cd in enumerate(cards, 1):
        f.write(f"{i}\n{ts(cd['start'])} --> {ts(cd['end'])}\n{cd['text']}\n\n")
