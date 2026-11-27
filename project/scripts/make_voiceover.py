"""Narration: Kokoro-82M neural TTS (Apache-2.0, run locally) -> timed, processed 48 kHz voice track.

Also runs an independent ASR (sherpa-onnx Zipformer, Apache-2.0) over every line to
  1) obtain word timestamps for the word-by-word subtitles, and
  2) verify the narration is intelligible (transcript compared against the script).
Writes audio/voiceover/narration_processed.wav, audio/voiceover/timing.json
"""
import json, os, re, numpy as np, soundfile as sf
from scipy import signal
from kokoro_onnx import Kokoro

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VO = os.path.join(ROOT, "audio/voiceover")
os.makedirs(VO, exist_ok=True)
SR = 48000
TOTAL = 30.0

LINES = [  # (slot start, slot end, text, list of sub-phrases with pause after)
    (0.0, 5.0, "Every night, when you fall asleep, your body begins an extraordinary transformation."),
    (5.0, 11.0, "Your brain cycles through different stages, organizing memories and processing information."),
    (11.0, 17.0, "Deep inside, a cleansing system helps move waste products out of brain tissue."),
    (17.0, 23.0, "Your heartbeat and breathing slow, while your body regulates hormones and supports tissue repair."),
    (23.0, 30.0, "And while you dream, your brain remains active. Sleep isn't wasted time. It's essential maintenance."),
]
STARTS = [0.30, 5.20, 11.15, 17.05, 22.80]   # chosen so each line sits inside its scene slot
MAX_LEN = [4.75, 5.75, 5.70, 5.80, 6.80]      # line must end before next slot / fade-out

k = Kokoro(os.path.join(ROOT, "tools/models/kokoro-v1.0.int8.onnx"), os.path.join(ROOT, "tools/models/voices-v1.0.bin"))
voice = 0.65 * k.get_voice_style("am_michael") + 0.35 * k.get_voice_style("am_onyx")


def synth(text, speed):
    if text.startswith("And while you dream"):
        parts = ["And while you dream, your brain remains active.", "Sleep isn't wasted time.", "It's essential maintenance."]
        gaps = [0.30, 0.22]
        out = []
        for i, p in enumerate(parts):
            a, sr = k.create(p, voice=voice, speed=speed, lang="en-us")
            out.append(a)
            if i < len(gaps):
                out.append(np.zeros(int(gaps[i] * sr), np.float32))
        return np.concatenate(out), sr
    return k.create(text, voice=voice, speed=speed, lang="en-us")


def trim(a, sr, thr=0.008):
    env = np.abs(a)
    idx = np.where(env > thr)[0]
    s = max(0, idx[0] - int(0.02 * sr)); e = min(len(a), idx[-1] + int(0.06 * sr))
    return a[s:e]


raw = []
for (s0, s1, text), mx in zip(LINES, MAX_LEN):
    speed = 0.94  # slightly slower than default for a calm documentary read
    while True:
        a, sr = synth(text, speed)
        a = trim(a, sr)
        if len(a) / sr <= mx or speed > 1.25:
            break
        speed += 0.02
    print(f"{len(a)/sr:5.2f}s  speed={speed:.2f}  {text}")
    a48 = signal.resample_poly(a, 2, 1).astype(np.float32)  # 24k -> 48k
    raw.append((a48, speed))

# ------------------------------------------------------------------ processing chain
def biquad(kind, f0, q=0.707, gain_db=0.0):
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / SR; al = np.sin(w) / (2 * q); c = np.cos(w)
    if kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]; a = [1 + al, -2 * c, 1 - al]
    elif kind == "peak":
        b = [1 + al * A, -2 * c, 1 - al * A]; a = [1 + al / A, -2 * c, 1 - al / A]
    elif kind == "lowshelf":
        sq = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    elif kind == "highshelf":
        sq = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
        a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    return np.array(b) / a[0], np.array(a) / a[0]


def eq(x, chain):
    for args in chain:
        b, a = biquad(*args); x = signal.lfilter(b, a, x)
    return x


def compress(x, thr_db=-20, ratio=3.0, att=0.008, rel=0.12, makeup_db=4):
    env = np.zeros_like(x); e = 0.0
    aa = np.exp(-1 / (att * SR)); ar = np.exp(-1 / (rel * SR))
    ax = np.abs(x)
    for i in range(len(x)):
        v = ax[i]; e = aa * e + (1 - aa) * v if v > e else ar * e + (1 - ar) * v; env[i] = e
    lvl = 20 * np.log10(env + 1e-9)
    gr = np.minimum(0, (thr_db - lvl) * (1 - 1 / ratio))
    return x * 10 ** ((gr + makeup_db) / 20)


def deess(x):
    b, a = signal.butter(2, [5500 / (SR / 2), 9000 / (SR / 2)], "band")
    s = signal.lfilter(b, a, x)
    env = signal.lfilter([0.002], [1, -0.998], np.abs(s))
    g = np.clip(1 - np.maximum(0, env - 0.012) * 18, 0.5, 1)
    return x - s * (1 - g)


rng = np.random.default_rng(7)
ir_len = int(0.55 * SR)
t = np.arange(ir_len) / SR
ir = rng.standard_normal(ir_len) * np.exp(-t / 0.11)
ir = signal.lfilter(*signal.butter(2, 4500 / (SR / 2)), ir)
ir[: int(0.012 * SR)] = 0  # pre-delay
ir /= np.sqrt((ir ** 2).sum())

track = np.zeros(int(TOTAL * SR), np.float32)
for (a, sp), st in zip(raw, STARTS):
    i = int(st * SR); track[i:i + len(a)] += a[: len(track) - i]
x = eq(track.astype(np.float64), [("hp", 75, 0.7), ("lowshelf", 220, 0.7, 2.5), ("peak", 450, 1.0, -1.5),
                                  ("peak", 3200, 0.9, 2.0), ("highshelf", 10000, 0.7, 1.0)])
x = deess(x)
x = compress(x)
wet = signal.fftconvolve(x, ir)[: len(x)]
x = x + 0.10 * wet
x = x / (np.abs(x).max() + 1e-9) * 10 ** (-3 / 20)
sf.write(os.path.join(VO, "narration_processed.wav"), x.astype(np.float32), SR, subtype="PCM_24")
for i, ((a, sp), st) in enumerate(zip(raw, STARTS)):
    sf.write(os.path.join(VO, f"line_{i+1}_raw.wav"), a, SR, subtype="PCM_24")

# ------------------------------------------------------------------ ASR word timing + intelligibility
import sherpa_onnx
md = [d for d in os.listdir(os.path.join(ROOT, "tools/asr")) if d.startswith("sherpa")][0]
md = os.path.join(ROOT, "tools/asr", md)
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{md}/encoder-epoch-99-avg-1.int8.onnx", decoder=f"{md}/decoder-epoch-99-avg-1.int8.onnx",
    joiner=f"{md}/joiner-epoch-99-avg-1.int8.onnx", tokens=f"{md}/tokens.txt", num_threads=4)


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower())


timing = {"lines": []}
for li, ((a, sp), st, (s0, s1, text)) in enumerate(zip(raw, STARTS, LINES)):
    a16 = signal.resample_poly(a, 1, 3).astype(np.float32)
    pad = np.zeros(int(0.3 * 16000), np.float32)
    stream = rec.create_stream(); stream.accept_waveform(16000, np.concatenate([pad, a16, pad]))
    rec.decode_stream(stream)
    r = stream.result
    toks, ts = list(r.tokens), list(r.timestamps)
    # assemble ASR words from BPE pieces ("▁" marks word start)
    asr_words = []
    for tk, tt in zip(toks, ts):
        tt = tt - 0.3
        if tk.startswith("▁") or not asr_words:
            asr_words.append([tk.replace("▁", ""), tt])
        else:
            asr_words[-1][0] += tk
    script_words = text.split()
    # align script words to ASR words with difflib on normalised strings
    import difflib
    sw = [norm(w) for w in script_words]; aw = [norm(w[0]) for w in asr_words]
    sm = difflib.SequenceMatcher(a=sw, b=aw, autojunk=False)
    starts = [None] * len(sw)
    for blk in sm.get_matching_blocks():
        for k_ in range(blk.size):
            starts[blk.a + k_] = asr_words[blk.b + k_][1]
    # also accept fuzzy matches inside replaced ranges by position
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            for n_ in range(i2 - i1):
                if j1 + n_ < j2:
                    starts[i1 + n_] = asr_words[j1 + n_][1]
    dur = len(a) / SR
    # interpolate any missing starts
    known = [(i, s) for i, s in enumerate(starts) if s is not None]
    for i in range(len(starts)):
        if starts[i] is None:
            prev = max([k for k in known if k[0] < i], default=(-1, 0.0), key=lambda k: k[0])
            nxt = min([k for k in known if k[0] > i], default=(len(starts), dur), key=lambda k: k[0])
            starts[i] = prev[1] + (nxt[1] - prev[1]) * (i - prev[0]) / (nxt[0] - prev[0])
    starts = [max(0.0, s - 0.04) for s in starts]  # ASR token times lag the onset slightly
    words = []
    for i, w in enumerate(script_words):
        ws = st + starts[i]
        we = st + (starts[i + 1] if i + 1 < len(starts) else dur)
        words.append({"word": w, "start": round(ws, 3), "end": round(we, 3)})
    transcript = " ".join(w[0] for w in asr_words).lower()
    wer_ref = " ".join(sw)
    ratio = difflib.SequenceMatcher(a=wer_ref.split(), b=[norm(x) for x in transcript.split()]).ratio()
    print(f"line {li+1} ASR: {transcript}\n        match ratio {ratio:.2f}")
    timing["lines"].append({"text": text, "start": st, "end": round(st + dur, 3), "speed": sp,
                            "asr_transcript": transcript, "asr_match_ratio": round(ratio, 3), "words": words})
json.dump(timing, open(os.path.join(VO, "timing.json"), "w"), indent=1)
print("wrote", os.path.join(VO, "timing.json"))
