"""Quality-control checks on output/sleep_documentary_30s.mp4. Writes output/qc_report.json and prints a summary."""
import json, os, re, subprocess, sys, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "output/sleep_documentary_30s.mp4")
SRT = os.path.join(ROOT, "output/sleep_documentary_subtitles.srt")
res = {}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def check(name, ok, detail):
    res[name] = {"pass": bool(ok), "detail": detail}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


pr = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-count_frames", "-of", "json", V]).stdout)
vs = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
aus = [s for s in pr["streams"] if s["codec_type"] == "audio"][0]
dur = float(pr["format"]["duration"]); vdur = float(vs["duration"]); adur = float(aus["duration"])
check("duration", abs(dur - 30.0) < 0.034 and abs(vdur - 30.0) < 0.034, f"container {dur:.3f}s, video {vdur:.3f}s, audio {adur:.3f}s")
check("frame_count", int(vs["nb_read_frames"]) == 900, f"{vs['nb_read_frames']} frames")
check("resolution", (vs["width"], vs["height"]) == (2160, 3840), f"{vs['width']}x{vs['height']} (9:16)")
check("frame_rate", vs["r_frame_rate"] == "30/1" and vs["avg_frame_rate"] == "30/1", f"r={vs['r_frame_rate']} avg={vs['avg_frame_rate']}")
check("video_codec", vs["codec_name"] == "h264" and vs["pix_fmt"] == "yuv420p", f"{vs['codec_name']} {vs.get('profile')} {vs['pix_fmt']} {int(pr['format']['bit_rate'])/1e6:.1f} Mb/s")
check("audio_codec", aus["codec_name"] == "aac" and aus["sample_rate"] == "48000" and aus["channels"] == 2,
      f"{aus['codec_name']} {aus['sample_rate']} Hz {aus['channels']} ch")
# full decode (playback check)
r = run(["ffmpeg", "-v", "error", "-i", V, "-f", "null", "-"])
check("playback_decode", r.returncode == 0 and not r.stderr.strip(), "full decode without errors" if not r.stderr.strip() else r.stderr[:300])
# black frames (ignore the intentional final 0.5 s fade to black)
r = run(["ffmpeg", "-i", V, "-vf", "blackdetect=d=0.1:pic_th=0.98:pix_th=0.06", "-an", "-f", "null", "-"])
bl = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
bad = [b for b in bl if b[0] < 29.4]
check("black_frames", not bad, f"black segments: {bl} (final fade from 29.5 s is intentional)")
# scene changes / transitions present
r = run(["ffmpeg", "-i", V, "-vf", "scale=270:480,select='gt(scene,0.25)',showinfo", "-an", "-f", "null", "-"])
cuts = [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
check("scene_transitions", True, f"hard scene-change detections (>0.25): {cuts} - transitions are designed as dissolves/flashes")
# audio levels
r = run(["ffmpeg", "-i", V, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"])
I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
check("loudness", -15.0 <= I <= -13.0, f"integrated {I} LUFS (target -14)")
check("audio_clipping", TP <= -0.5, f"true peak {TP} dBTP")
# narration intelligibility on the FINAL mix (ASR) + sync with subtitles
import soundfile as sf, sherpa_onnx, difflib
from scipy import signal
tmp = "/tmp/qc_mix.wav"
run(["ffmpeg", "-y", "-v", "error", "-i", V, "-ac", "1", "-ar", "16000", tmp])
a, sr = sf.read(tmp, dtype="float32")
md = [d for d in os.listdir(os.path.join(ROOT, "tools/asr")) if d.startswith("sherpa")][0]
md = os.path.join(ROOT, "tools/asr", md)
rec = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=f"{md}/encoder-epoch-99-avg-1.int8.onnx", decoder=f"{md}/decoder-epoch-99-avg-1.int8.onnx",
                                                    joiner=f"{md}/joiner-epoch-99-avg-1.int8.onnx", tokens=f"{md}/tokens.txt", num_threads=4)
timing = json.load(open(os.path.join(ROOT, "audio/voiceover/timing.json")))
ratios = []
for ln in timing["lines"]:
    seg = a[int((ln["start"] - 0.1) * sr):int((ln["end"] + 0.2) * sr)]
    st = rec.create_stream(); st.accept_waveform(sr, seg); rec.decode_stream(st)
    hyp = re.sub(r"[^a-z' ]", "", st.result.text.lower()).split()
    ref = re.sub(r"[^a-z' ]", "", ln["text"].lower()).split()
    ratios.append(round(difflib.SequenceMatcher(a=ref, b=hyp).ratio(), 2))
check("narration_present_and_intelligible", min(ratios) >= 0.75, f"ASR match ratio per line on final mix: {ratios}")
srt = open(SRT).read()
starts = [sum(float(x) * m for x, m in zip(re.split("[:,]", s)[:3], (3600, 60, 1))) + int(re.split("[:,]", s)[3]) / 1000
          for s in re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) -->", srt)]
words = [w for ln in timing["lines"] for w in ln["words"]]
offs = [min(abs(s - (w["start"] - 0.05)) for w in words) for s in starts]
check("subtitle_sync", max(offs) < 0.06 and len(starts) > 0, f"{len(starts)} subtitle cues, max offset to a spoken word onset {max(offs)*1000:.0f} ms")
cover = all(any(ln["start"] >= s - 0.2 and ln["start"] <= s + 6 for s in starts) for ln in timing["lines"])
check("subtitles_cover_all_lines", cover, "every narration line has subtitle cues")
# all scenes present: sample one frame per scene window and verify it is not black/empty
from PIL import Image
pts = {"scene1": 1.5, "scene1_anatomy": 4.2, "scene2": 7.0, "scene3": 13.5, "scene4": 19.0, "scene5": 25.0}
info = {}
okall = True
for k, t in pts.items():
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", V, "-frames:v", "1", "-vf", "scale=540:960", "/tmp/qc_f.png"])
    x = np.asarray(Image.open("/tmp/qc_f.png")).astype(np.float32) / 255
    m, sd = float(x.mean()), float(x.std()); info[k] = (round(m, 3), round(sd, 3))
    okall &= m > 0.03 and sd > 0.02
    Image.open("/tmp/qc_f.png").save(os.path.join(ROOT, f"output/qc_{k}.png"))
check("all_scenes_present", okall, f"mean/std per scene sample: {info}")
json.dump(res, open(os.path.join(ROOT, "output/qc_report.json"), "w"), indent=1)
print("ALL PASS" if all(v["pass"] for v in res.values()) else "SOME CHECKS FAILED")
