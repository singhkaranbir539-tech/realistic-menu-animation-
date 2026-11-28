"""Narration with the ElevenLabs "Adam" voice (one request per scene, with
character timestamps). Writes the same files as tts.py: build/narration.wav,
build/timing.json, build/envelope.json, build/captions.json, output/subtitles.srt.

The API key is never in code: the session's network proxy injects it into
requests to api.elevenlabs.io (locally, export ELEVENLABS_API_KEY instead)."""
import base64, io, json, os, re, subprocess, sys, urllib.request
import numpy as np, soundfile as sf

ROOT = sys.path[0] + "/.."
SR, FPS, TOTAL = 24000, 30, 172
VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam
KEY = os.environ.get("ELEVENLABS_API_KEY", "proxy-injected")
CACHE = f"{ROOT}/build/el"; os.makedirs(CACHE, exist_ok=True)
scenes = json.load(open(f"{ROOT}/scenes.json"))

def spoken(s):  # one spoken token per written word, so word timings map 1:1
    return s.replace("MA30", "MA-30")

def synth(text, speed, sid):
    path = f"{CACHE}/scene_{sid:02}_{speed:.3f}.json"
    if os.path.exists(path):
        return json.load(open(path))
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.32, "similarity_boost": 0.85, "style": 0.55,
                           "use_speaker_boost": True, "speed": round(speed, 3)}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=180))
    json.dump(res, open(path, "w"))
    return res

def decode(b64):
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "-", "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         input=base64.b64decode(b64), capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.float32).copy()

out = np.zeros(SR * TOTAL, dtype=np.float32)
timing, words_all = [], []
for sc in scenes:
    avail = sc["end"] - sc["start"] - 1.3
    speed = 1.0
    for _ in range(3):
        res = synth(spoken(sc["text"]), speed, sc["id"])
        al = res["alignment"]; audio = decode(res["audio_base64"])
        dur = al["character_end_times_seconds"][-1]
        if dur <= avail or speed >= 1.2: break
        speed = min(1.2, speed * dur / avail * 1.02)
    # trim leading silence so the scene offset is exact
    lead = al["character_start_times_seconds"][0]
    # word timings from character alignment
    chars, cs, ce = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    words, cur = [], None
    for ch, a, b in zip(chars, cs, ce):
        if ch.isspace():
            if cur: words.append(cur); cur = None
        else:
            cur = [cur[0] + ch, cur[1], b] if cur else [ch, a, b]
    if cur: words.append(cur)
    disp = sc["text"].split()
    assert len(disp) == len(words), (sc["id"], len(disp), len(words))
    t0 = sc["start"] + 0.7 + max(0, (avail - (dur - lead)) * 0.35) - lead
    i = int(t0 * SR); out[i:i + len(audio)] += audio[: len(out) - i]
    W = [{"w": d, "start": round(t0 + a, 3), "end": round(t0 + b, 3), "scene": sc["id"]} for d, (_, a, b) in zip(disp, words)]
    words_all += W
    # clauses (same split as the renderer expects)
    k = 0
    for c in [c for c in re.split(r"(?<=[.,])\s+", sc["text"]) if c.strip()]:
        n = len(c.split()); seg = W[k:k + n]; k += n
        timing.append({"scene": sc["id"], "text": c, "start": seg[0]["start"], "end": seg[-1]["end"]})
    print(f"scene {sc['id']}: speed {speed:.3f}, speech {dur - lead:.2f}s of {sc['end'] - sc['start']}s")

out = out / np.max(np.abs(out)) * 0.89
sf.write(f"{ROOT}/build/narration.wav", out, SR)
json.dump(timing, open(f"{ROOT}/build/timing.json", "w"), indent=1)
json.dump(words_all, open(f"{ROOT}/build/words.json", "w"))
hop = SR // FPS
rms = np.array([np.sqrt(np.mean(out[i * hop:(i + 1) * hop] ** 2)) for i in range(TOTAL * FPS)])
rms = np.convolve(rms, [0.25, 0.5, 0.25], "same")
env = np.clip(rms / np.percentile(rms[rms > 0.01], 90), 0, 1.0)
json.dump([round(float(x), 3) for x in env], open(f"{ROOT}/build/envelope.json", "w"))

# caption cards: <=5 words, never across a clause boundary, exact word times
cards = []
for c in timing:
    ws = [w for w in words_all if w["scene"] == c["scene"] and c["start"] <= w["start"] <= c["end"]]
    groups, g = [], []
    for w in ws:
        g.append(w)
        if len(g) >= 5 or (len(g) >= 3 and len(" ".join(x["w"] for x in g)) > 26):
            groups.append(g); g = []
    if g:
        if groups and len(g) <= 1: groups[-1] += g
        else: groups.append(g)
    for g in groups:
        cards.append({"scene": c["scene"], "text": " ".join(x["w"] for x in g), "start": g[0]["start"], "end": g[-1]["end"]})
json.dump(cards, open(f"{ROOT}/build/captions.json", "w"), indent=1)
def ts(x):
    return f"{int(x // 3600):02}:{int(x % 3600 // 60):02}:{x % 60:06.3f}".replace(".", ",")
with open(f"{ROOT}/output/subtitles.srt", "w") as f:
    for i, cd in enumerate(cards, 1):
        f.write(f"{i}\n{ts(cd['start'])} --> {ts(cd['end'])}\n{cd['text']}\n\n")
print("ok")
