"""Scene 5 - THE POWER OF SLEEP (7 s = 210 frames).

The CT-derived glass anatomical figure stands in a deep midnight-blue void (brain with soft neural
activity, heart beating, lungs breathing), then slowly reclines into a sleeping position while the
camera pulls back. The final fade to black is applied in compositing.
usage: python3 scene_05.py -- still 1 100 210 | python3 scene_05.py -- render 1 210
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import anatomy

ARGS = args()
s = reset(res=(720, 1280), samples=26)
s.cycles.adaptive_threshold = 0.045
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2; s.cycles.transparent_max_bounces = 20
s.render.use_persistent_data = True
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1
# pivot at the pelvis; CT coords are already Z-up (anterior = -Y)
pivot = empty("Pivot", (0, 0, 0.0))
body = empty("Body", (0, 0, 0)); body.parent = pivot
objs = anatomy.build(body, skeleton_alpha=0.4)
anatomy.void_world(s, top=(0.008, 0.016, 0.045))
anatomy.dust(240, ((-1.5, 1.5), (-1.5, 2.0), (-1.0, 2.0)), seed=21, strength=0.8)
CHEST = Vector((0.02, 0.0, 0.43))
light("AREA", "Key", (-0.9, -1.2, 1.4), 120, color=(0.6, 0.8, 1.0), size=1.5, target=CHEST)
light("AREA", "RimV", (0.9, 0.9, 1.1), 170, color=(0.55, 0.4, 1.0), size=1.2, target=CHEST)
light("AREA", "RimC", (-0.9, 0.9, 0.4), 120, color=(0.25, 0.75, 1.0), size=1.2, target=CHEST)
light("POINT", "Inner", (0.02, 0.0, 0.43), 1.5, color=(1.0, 0.35, 0.3), size=0.05)
# slow atmospheric light movement
mover = light("AREA", "Drift", (1.2, -0.6, 1.6), 60, color=(0.4, 0.55, 1.0), size=1.0, target=CHEST)
for f, loc in [(1, (1.2, -0.6, 1.6)), (210, (-0.4, -1.2, 1.9))]:
    key(mover, "location", f, Vector(loc))

tgt = empty("CamTarget", CHEST)
cam = camera(lens=35, loc=(-0.25, -0.75, 0.55), fstop=4.0, focus_obj=tgt); track_to(cam, tgt)
# standing -> reclining (rotate about the pelvis), camera pulls back and rises
for f, rx in [(1, 0.0), (70, 0.0), (190, -88.0), (210, -90.0)]:
    key(pivot, "rotation_euler", f, Euler((math.radians(rx), 0, math.radians(-14))))
pivot_loc = [(1, (0, 0, 0)), (70, (0, 0, 0)), (210, (0, 0.0, 0.15))]
for f, loc in pivot_loc:
    key(pivot, "location", f, Vector(loc))
for f, loc, t_, lens, fs in [(1, (-0.30, -0.70, 0.62), Vector((0.0, 0.0, 0.60)), 35, 4.0),
                              (70, (-0.42, -1.05, 0.62), Vector((0.0, 0.0, 0.48)), 35, 5.0),
                              (150, (-0.55, -1.25, 1.10), Vector((0.0, 0.25, 0.20)), 35, 6.0),
                              (210, (-0.50, -1.10, 1.60), Vector((0.0, 0.40, 0.15)), 35, 7.0)]:
    key(cam, "location", f, Vector(loc)); key(tgt, "location", f, t_)
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
for idb in (pivot, cam, tgt, cam.data, mover):
    set_interp(idb, "BEZIER")
# the shell's edge glow softens as the body settles into sleep
eg = objs["Shell"].data.materials[0].node_tree.nodes["EdgeGain"]
for f, v in [(1, 1.3), (120, 1.0), (210, 0.6)]:
    eg.outputs[0].default_value = v; eg.outputs[0].keyframe_insert("default_value", frame=f)

mode = ARGS[0] if ARGS else "still"
if mode == "still":
    os.makedirs("/tmp/claude-0/x/s5", exist_ok=True)
    for f in [int(a) for a in ARGS[1:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"/tmp/claude-0/x/s5/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, "renders/scene_renders/scene_05"), int(ARGS[1]), int(ARGS[2]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
