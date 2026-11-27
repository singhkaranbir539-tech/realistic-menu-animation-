"""Re-edit scene 4 to remove interpolation jump cuts.

The fast-mode render (15 fps + minterpolate) cannot bridge the camera passing the white blood cell
(~src 119) or the final dive into the muscle fibres (src >150). Edit: vessel flight src 1-100,
12-frame dissolve into the muscle-fibre shot (src 126-148), which is slowed to ~0.21x with FFmpeg
motion-compensated interpolation. Output: renders/scene_renders/scene_04_edit/f_0001..f_0186.png
"""
import os, subprocess, tempfile, shutil
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "renders/scene_renders")
SRC = os.path.join(R, "scene_04_30")
OUT = os.path.join(R, "scene_04_edit")
N, A_END, DISS = 186, 100, 12
B0, B1 = 126, 148

tmp = tempfile.mkdtemp()
for j, k in enumerate(range(B0, B1 + 1)):
    os.symlink(os.path.join(SRC, f"f_{k:04d}.png"), os.path.join(tmp, f"s_{j:04d}.png"))
bdir = os.path.join(tmp, "b"); os.makedirs(bdir)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", os.path.join(tmp, "s_%04d.png"),
                "-vf", "minterpolate=fps=140:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                "-pix_fmt", "rgb48be", "-start_number", "1", os.path.join(bdir, "b_%04d.png")], check=True)
nb = len(os.listdir(bdir))
need = N - (A_END - DISS)
print("slow-mo frames available", nb, "needed", need)

def load(p):
    a = np.asarray(Image.open(p)).astype(np.float32)
    return a / (65535.0 if a.max() > 255 else 255.0)

def save(a, p):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p)   # 12 dissolve frames only

shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
for i in range(1, N + 1):
    bi = i - (A_END - DISS)            # index into B (1-based) once B has started
    bp = os.path.join(bdir, f"b_{min(max(bi, 1), nb):04d}.png")
    if i <= A_END - DISS:
        os.symlink(os.path.join(SRC, f"f_{i:04d}.png"), os.path.join(OUT, f"f_{i:04d}.png"))
    elif i <= A_END:
        t = (i - (A_END - DISS)) / (DISS + 1); t = t * t * (3 - 2 * t)
        save(load(os.path.join(SRC, f"f_{i:04d}.png")) * (1 - t) + load(bp)[..., :3] * t, os.path.join(OUT, f"f_{i:04d}.png"))
    else:
        shutil.copy(bp, os.path.join(OUT, f"f_{i:04d}.png"))
shutil.rmtree(tmp)
print("wrote", len(os.listdir(OUT)), "frames")
