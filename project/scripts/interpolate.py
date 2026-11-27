"""Rebuild 30 fps sequences for shots rendered at every 2nd frame (15 fps) using FFmpeg's
motion-compensated interpolation (minterpolate, mci/aobmc). Output: renders/scene_renders/<shot>_30/f_####.png
where f_k corresponds to source frame k. usage: python3 interpolate.py shot [shot ...]"""
import os, sys, subprocess, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "renders/scene_renders")
for shot in sys.argv[1:]:
    src = os.path.join(R, shot)
    frames = sorted(f for f in os.listdir(src) if f.endswith(".png") and os.path.getsize(os.path.join(src, f)) > 0)
    nums = [int(f[2:6]) for f in frames]
    if all(n % 2 == 1 for n in nums) is False or len(nums) < 2:
        print(shot, "not a 2-step sequence, skipping"); continue
    tmp = tempfile.mkdtemp()
    for k, f in enumerate(frames):
        os.symlink(os.path.join(src, f), os.path.join(tmp, f"s_{k:04d}.png"))
    out = os.path.join(R, shot + "_30"); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "15", "-i", os.path.join(tmp, "s_%04d.png"),
                    "-vf", "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                    "-pix_fmt", "rgb48be", "-start_number", str(nums[0]), os.path.join(out, "f_%04d.png")], check=True)
    shutil.rmtree(tmp)
    print(shot, len(frames), "->", len(os.listdir(out)), "frames")
