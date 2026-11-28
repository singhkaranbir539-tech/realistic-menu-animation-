"""Concatenate rendered segments, mux the final mix, burn subtitles, export deliverables.
   python3 scripts/assemble.py h     -> landscape outputs
   python3 scripts/assemble.py v     -> vertical outputs
"""
import glob, json, os, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
mode = sys.argv[1]
out = f"{ROOT}/output"; os.makedirs(out, exist_ok=True)
DUR = json.load(open(f"{ROOT}/storyboard/shots.json"))["duration"]
def run(c): print(" ".join(c[:6]), "..."); subprocess.run(c, check=True)
segs = sorted(glob.glob(f"{ROOT}/renders/{mode}/seg_[0-9][0-9][0-9].mp4"))
lst = f"{ROOT}/renders/{mode}/concat.txt"
open(lst, "w").write("".join(f"file '{s}'\n" for s in segs))
video = f"{ROOT}/renders/{mode}/video_only.mp4"
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
AUD = f"{ROOT}/audio/final_mix.wav"
ENC = ["-c:v", "libx264", "-preset", "slow", "-pix_fmt", "yuv420p", "-profile:v", "high", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
       "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{DUR}", "-r", "30"]
fontdir = f"{ROOT}/assets/fonts"
if mode == "h":
    ass = f"{ROOT}/subtitles/landscape_1080p.ass"
    # 1080p native masters
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", *ENC, "-crf", "17", f"{out}/muscle_growth_documentary_1080p_clean_master.mp4"])
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", "-vf", f"ass={ass}:fontsdir={fontdir}", *ENC, "-crf", "17", f"{out}/muscle_growth_documentary_1080p_subtitled_master.mp4"])
    # 4K: high-quality Lanczos upscale of the native 1080p render (clearly labelled)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", "-vf",
         f"scale=3840:2160:flags=lanczos,unsharp=5:5:0.35:5:5:0.0,ass={ass}:fontsdir={fontdir}:original_size=1920x1080", *ENC, "-crf", "18", f"{out}/muscle_growth_documentary_4K_UPSCALED_subtitled_master.mp4"])
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", "-vf",
         "scale=3840:2160:flags=lanczos,unsharp=5:5:0.35:5:5:0.0", *ENC, "-crf", "18", f"{out}/muscle_growth_documentary_4K_UPSCALED_clean_master.mp4"])
    # size-capped copies small enough for the git repository (<95 MB)
    for kind, vf in (("clean", None), ("subtitled", f"ass={ass}:fontsdir={fontdir}")):
        c = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a"] + (["-vf", vf] if vf else []) + ENC
        c = [x for x in c]; i = c.index("320k"); c[i] = "192k"
        run(c + ["-b:v", "3800k", "-maxrate", "4200k", "-bufsize", "8400k", f"{out}/muscle_growth_documentary_1080p_{kind}.mp4"])
else:
    ass = f"{ROOT}/subtitles/vertical_1080x1920.ass"
    up = "scale=1080:1920:flags=lanczos,unsharp=5:5:0.3:5:5:0.0"
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", "-vf", f"{up},ass={ass}:fontsdir={fontdir}", *ENC, "-crf", "18", f"{out}/muscle_growth_documentary_vertical_1080x1920_UPSCALED_subtitled_master.mp4"])
    c = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", AUD, "-map", "0:v", "-map", "1:a", "-vf", f"{up},ass={ass}:fontsdir={fontdir}"] + ENC
    c[c.index("320k")] = "192k"
    run(c + ["-b:v", "3800k", "-maxrate", "4200k", "-bufsize", "8400k", f"{out}/muscle_growth_documentary_vertical_1080x1920_UPSCALED_subtitled.mp4"])
print("done")
