"""Scene 1B - inside view: the same side-lying body as a glass anatomical figure (frames 1-78).

Starts where 1A ends (behind the head), pulls back and arcs over the body to reveal the CT-derived
skeleton, heart (beating), lungs (breathing), organs and cortex, then travels toward the head.
usage: python3 scene_01b.py -- still 1 40 78 | python3 scene_01b.py -- render 1 78
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import anatomy, numpy as np

ARGS = args()
s = reset(res=(720, 1280), samples=28)
s.cycles.adaptive_threshold = 0.045
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2
s.cycles.transparent_max_bounces = 14
s.render.motion_blur_shutter = 0.2
s.render.use_persistent_data = True
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1
M = 0.55
ROLL = math.radians(72)
person = empty("Person", (0, 0, 0)); person.rotation_euler = (math.radians(-90), ROLL, 0)
objs = anatomy.build(person, skeleton_alpha=0.62, decimate_skin=0.3)
sk = objs["Shell"]
bpy.context.view_layer.update()
# same placement as 1A (computed from the full-res skin there; replicate using the shell)
co = np.empty(len(sk.data.vertices) * 3, np.float32); sk.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
mw = np.array(sk.matrix_world); wco = co @ mw[:3, :3].T + mw[:3, 3]
head = co[:, 2] > 0.60
person.location.z = (M + 0.15) - 0.03 - wco[head, 2].min()
bpy.context.view_layer.update()
mw = np.array(sk.matrix_world); wco = co @ mw[:3, :3].T + mw[:3, 3]
HEAD_C = Vector(wco[head].mean(0))
CHEST = Vector(wco[(co[:, 2] > 0.36) & (co[:, 2] < 0.5)].mean(0))
pz0 = person.location.z
fcp = person.driver_add("location", 2); fcp.driver.expression = f"{pz0}+0.0012*sin(frame*0.0524)"
anatomy.void_world(s, top=(0.006, 0.014, 0.035))
anatomy.dust(90, ((-1.2, 1.2), (-0.8, 1.6), (0.2, 2.0)), seed=11)
# faint ghost of the bed surface below (keeps spatial continuity with 1A)


light("AREA", "Key", (-0.6, 0.0, 1.9), 90, color=(0.6, 0.8, 1.0), size=1.2, target=CHEST)
light("AREA", "RimV", (0.9, 1.4, 1.2), 120, color=(0.55, 0.4, 1.0), size=1.0, target=CHEST)
light("AREA", "Front", (1.0, 0.1, 1.2), 45, color=(0.4, 0.75, 1.0), size=1.0, target=CHEST)
light("POINT", "Inner", CHEST + Vector((0.02, 0, 0)), 2.0, color=(1.0, 0.35, 0.3), size=0.05)

tgt = empty("CamTarget", HEAD_C)
cam = camera(lens=55, loc=(-0.24, 0.57, HEAD_C.z + 0.09), fstop=2.8, focus_obj=tgt); track_to(cam, tgt)
NAPE = HEAD_C + Vector((-0.07, -0.06, -0.01))
SHOULDER = Vector((HEAD_C.x - 0.10, HEAD_C.y - 0.26, HEAD_C.z - 0.02))
for f, loc, t_, lens, fs in [(1, (-0.42, 0.02, M + 0.33), SHOULDER + Vector((0.02, 0.14, 0.03)), 45, 2.8),
                              (40, (-0.45, 0.02, 1.55), CHEST + Vector((0, 0.05, 0)), 32, 5.6),
                              (72, (0.50, -0.05, 1.42), CHEST + Vector((0, 0.08, 0)), 32, 6.0),
                              (104, (0.10, 0.42, HEAD_C.z + 0.42), HEAD_C, 40, 5.0)]:
    key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
    cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
for idb in (cam, tgt, cam.data):
    set_interp(idb, "BEZIER")

mode = ARGS[0] if ARGS else "still"
if mode == "still":
    os.makedirs("/tmp/claude-0/x/s1b", exist_ok=True)
    for f in [int(a) for a in ARGS[1:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"/tmp/claude-0/x/s1b/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, "renders/scene_renders/scene_01b"), int(ARGS[1]), int(ARGS[2]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
