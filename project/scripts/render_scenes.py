"""Render every scene's PNG sequence with Blender Cycles (bpy module), resumable.

Each scene script skips frames that already exist (use_overwrite=False + placeholders), so this can be
re-run after an interruption.  usage: python3 render_scenes.py [shot ...]
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = {
    "scene_01a": ["scenes/scene_01_body/scene_01a.py", "--", "render", "1", "64"],
    "scene_01b": ["scenes/scene_01_body/scene_01b.py", "--", "render", "1", "104"],
    "scene_02": ["scenes/scene_02_brain/scene_02.py", "--", "render", "1", "156"],
    "shot2b": ["scenes/scene_03_memory/neural_tissue.py", "--", "shot2b", "render", "1", "40"],
    "shot3": ["scenes/scene_03_memory/neural_tissue.py", "--", "shot3", "render", "1", "186"],
    "scene_04": ["scenes/scene_04_repair/scene_04.py", "--", "render", "1", "186"],
    "scene_05": ["scenes/scene_05_sleep/scene_05.py", "--", "render", "1", "210"],
}
sel = sys.argv[1:] or list(JOBS)
for name in sel:
    t0 = time.time()
    od = os.path.join(ROOT, "renders/scene_renders", name); os.makedirs(od, exist_ok=True)
    for f in os.listdir(od):   # remove placeholders left by an interrupted render
        if f.endswith(".png") and os.path.getsize(os.path.join(od, f)) == 0:
            os.remove(os.path.join(od, f))
    log = open(os.path.join(ROOT, f"renders/scene_renders/{name}.log"), "a")
    print(f"[{time.strftime('%H:%M:%S')}] rendering {name}", flush=True)
    env = dict(os.environ)
    if name != "scene_02":
        env["FRAME_STEP"] = "2"; env["FAST"] = "1"
    r = subprocess.run([sys.executable, os.path.join(ROOT, JOBS[name][0])] + JOBS[name][1:], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
    n = len([f for f in os.listdir(os.path.join(ROOT, "renders/scene_renders", name)) if f.endswith(".png")])
    print(f"[{time.strftime('%H:%M:%S')}] {name}: exit {r.returncode}, {n} frames, {time.time()-t0:.0f}s", flush=True)
