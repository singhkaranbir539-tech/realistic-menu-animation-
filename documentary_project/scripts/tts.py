"""Narration + word-level timing.

The source MP4 was never supplied, so the narration is synthesised locally with
Kokoro (Apache-2.0) from input/script_source.json. Each clause is synthesised
separately, so clause start/end times are exact. Word boundaries inside a
clause are estimated from per-word phoneme counts and then snapped to the
nearest short-time energy minimum (+/-90 ms).

Outputs:
  audio/narration_raw.wav        48 kHz mono
  transcript/transcript.json     sections > clauses > words with timestamps
  transcript/transcript.srt      sentence-group subtitles
  transcript/words.srt           one word per cue
"""
import json, re, sys, os
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
from kokoro_onnx import Kokoro

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SR = 24000
TOTAL = 172.37
k = Kokoro("/home/user/tts/kokoro.onnx", "/home/user/tts/voices.bin")
voice = k.get_voice_style("am_michael") * 0.65 + k.get_voice_style("am_onyx") * 0.35
sections = json.load(open(f"{ROOT}/input/script_source.json"))
# stretch the last section so the programme lasts the brief's 172.37 s
sections[-1]["end"] = TOTAL

SPOKEN = {"MA30": "M A thirty", "Karbolyn": "Car-bo-lin"}


def pronounce(s):
    for a, b in SPOKEN.items():
        s = s.replace(a, b)
    return s


def word_weights(words):
    w = []
    for wd in words:
        ph = k.tokenizer.phonemize(pronounce(wd), "en-us").replace(" ", "")
        w.append(max(2, len(ph)) + (3 if re.search(r"[,.]$", wd) else 0))
    return np.array(w, float)


def align(clause, audio, t0):
    words = clause.split()
    wts = word_weights(words)
    n = len(audio)
    # cumulative phoneme proportion -> sample boundary guesses
    cuts = np.cumsum(wts)[:-1] / wts.sum() * n
    hop = 240  # 10 ms
    env = np.sqrt(np.convolve(audio ** 2, np.ones(hop) / hop, "same"))
    snapped = []
    for c in cuts:
        lo, hi = int(max(0, c - 0.09 * SR)), int(min(n - 1, c + 0.09 * SR))
        seg = env[lo:hi:48]
        snapped.append(lo + int(np.argmin(seg)) * 48 if len(seg) else int(c))
    bounds = [0] + sorted(snapped) + [n]
    mind = int(0.09 * SR)  # minimum word length; resolve squeezed boundaries
    for _ in range(3):
        for i in range(1, len(bounds) - 1):
            if bounds[i] - bounds[i - 1] < mind: bounds[i] = min(bounds[i - 1] + mind, (bounds[i - 1] + bounds[i + 1]) // 2)
        for i in range(len(bounds) - 2, 0, -1):
            if bounds[i + 1] - bounds[i] < mind: bounds[i] = max(bounds[i + 1] - mind, (bounds[i - 1] + bounds[i + 1]) // 2)
    out = []
    for i, wd in enumerate(words):
        out.append({"word": wd, "start": round(t0 + bounds[i] / SR, 3),
                    "end": round(t0 + bounds[i + 1] / SR, 3)})
    return out


track = np.zeros(int(SR * (TOTAL + 1)), np.float32)
result = []
for sc in sections:
    clauses = [c.strip() for c in re.split(r"(?<=[.,])\s+", sc["text"]) if c.strip()]
    avail = sc["end"] - sc["start"] - 1.2
    speed, gapk = 0.93, 1.0
    for _ in range(5):
        pieces = []
        for c in clauses:
            a, _ = k.create(pronounce(c), voice=voice, speed=speed, lang="en-us")
            nz = np.where(np.abs(a) > 0.008)[0]
            a = a[max(0, nz[0] - 200): nz[-1] + 1500]
            gap = (0.45 if c.endswith(".") else 0.17) * gapk
            pieces.append((c, a, gap))
        total = sum(len(a) / SR + g for _, a, g in pieces) - pieces[-1][2]
        if total <= avail:
            break
        speed *= total / avail * 1.02
        gapk *= 0.85
    t = sc["start"] + 0.6 + max(0, (avail - total) * 0.3)
    sec = {"id": sc["id"], "title": sc["title"], "start": sc["start"], "end": sc["end"],
           "keys": sc["keys"], "text": sc["text"], "clauses": []}
    for c, a, g in pieces:
        i = int(t * SR)
        track[i:i + len(a)] += a
        sec["clauses"].append({"text": c, "start": round(t, 3), "end": round(t + len(a) / SR, 3),
                               "words": align(c, a, t)})
        t += len(a) / SR + g
    print(f"section {sc['id']:2d}  speed {speed:.3f}  speech {total:5.2f}s of {sc['end']-sc['start']:.2f}s")
    result.append(sec)

track = track[: int(SR * TOTAL)]
track = track / np.max(np.abs(track)) * 0.89
sf.write(f"{ROOT}/audio/narration_raw.wav", resample_poly(track, 2, 1).astype(np.float32), 48000, subtype="PCM_24")

meta = {"source": "Synthesised narration (Kokoro TTS, am_michael/am_onyx blend). "
                  "The reference MP4 was not provided; text from input/script_source.json.",
        "timing_method": "clause-exact; words = phoneme-weighted split snapped to energy minima",
        "duration": TOTAL, "sections": result}
json.dump(meta, open(f"{ROOT}/transcript/transcript.json", "w"), indent=1)


def ts(x):
    h, r = divmod(x, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"


# subtitle cues: group words into <= 42 chars per line, <= 2 lines, split on clause ends
cues = []
for sec in result:
    for cl in sec["clauses"]:
        cur = []
        for w in cl["words"]:
            if cur and len(" ".join(x["word"] for x in cur + [w])) > 64:
                cues.append(cur); cur = []
            cur.append(w)
        if cur:
            cues.append(cur)
with open(f"{ROOT}/transcript/transcript.srt", "w") as f:
    for i, c in enumerate(cues, 1):
        f.write(f"{i}\n{ts(c[0]['start'])} --> {ts(c[-1]['end'])}\n{' '.join(x['word'] for x in c)}\n\n")
with open(f"{ROOT}/transcript/words.srt", "w") as f:
    i = 1
    for sec in result:
        for cl in sec["clauses"]:
            for w in cl["words"]:
                f.write(f"{i}\n{ts(w['start'])} --> {ts(w['end'])}\n{w['word']}\n\n"); i += 1
json.dump([[{"w": x["word"], "s": x["start"], "e": x["end"]} for x in c] for c in cues],
          open(f"{ROOT}/transcript/cues.json", "w"))
print("cues", len(cues))
