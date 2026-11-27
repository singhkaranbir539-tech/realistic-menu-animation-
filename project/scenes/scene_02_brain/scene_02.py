"""Scene 2A - THE BRAIN'S NIGHT SHIFT (brain orbit + macro push-in).

Hero brain = FreeSurfer fsaverage5 pial cortex (real MRI-derived folding) + TotalSegmentator brain
mask (gives cerebellum / brainstem, with procedural folia). Sulcal depth from FreeSurfer drives
colour (darker, vascular sulci). Electrical activity = travelling emissive wavefronts restricted to
gyral crowns, deliberately restrained in brightness.

usage: python3 scene_02.py -- still 1 80 150   |   python3 scene_02.py -- render 1 156
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import numpy as np

ARGS = args()
s = reset(res=(720, 1280), samples=28)
s.cycles.adaptive_threshold = 0.04
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2
s.render.use_persistent_data = True
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1

rig = empty("BrainRig", (0, 0, 0))
parts = []
for h in ("left", "right"):
    o = import_ply(A("brain", f"cortex_{h}_inbody.ply"), f"cortex_{h}")
    sulc = np.load(A("brain", f"sulc_{h}.npy"))
    # store sulcal depth as a point attribute (normalised: +1 deep sulcus, -1 gyral crown)
    at = o.data.attributes.new("sulc", "FLOAT", "POINT")
    sn = np.clip(sulc / 1.2, -1, 1).astype(np.float32)
    at.data.foreach_set("value", sn)
    sub = o.modifiers.new("sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
    parts.append(o)
cb = import_ply(A("human_anatomy", "brain_ct.ply"), "brain_stem_cerebellum")
# keep only CT-brain surface that is far from the folded cortex -> cerebellum + brainstem
import bmesh
from scipy.spatial import cKDTree
cv = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in parts])
tree = cKDTree(cv)
bm = bmesh.new(); bm.from_mesh(cb.data)
dist, _ = tree.query(np.array([v.co[:] for v in bm.verts]))
zc = np.array([v.co.z for v in bm.verts])
kill = [v for v, d_, z_ in zip(bm.verts, dist, zc) if d_ < 0.0055 or z_ > 0.722]
bmesh.ops.delete(bm, geom=kill, context="VERTS")
bm.to_mesh(cb.data); bm.free()
sm = cb.modifiers.new("smooth", "SMOOTH"); sm.iterations = 6; sm.factor = 0.8
center = Vector((0.004, -0.026, 0.731))
for o in parts + [cb]:
    o.location -= center
    o.parent = rig

# ------------------------------------------------------------------ tissue material
m, n, l = mat("BrainTissue")
b = n["Principled BSDF"]
attr = n.new("ShaderNodeAttribute"); attr.attribute_name = "sulc"
ramp = n.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.25; ramp.color_ramp.elements[0].color = (0.66, 0.47, 0.45, 1)  # gyral crown
ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (0.30, 0.10, 0.11, 1)  # deep sulcus
mr0 = n.new("ShaderNodeMapRange"); mr0.inputs["From Min"].default_value = -1; mr0.inputs["From Max"].default_value = 1
l.new(attr.outputs["Fact"] if "Fact" in attr.outputs else attr.outputs["Fac"], mr0.inputs["Value"])
l.new(mr0.outputs[0], ramp.inputs[0])
# surface vessels: thin dark-red veins following a distorted noise ridge pattern
tc = n.new("ShaderNodeTexCoord")
vn = n.new("ShaderNodeTexNoise"); vn.inputs["Scale"].default_value = 28; vn.inputs["Detail"].default_value = 3; vn.inputs["Distortion"].default_value = 1.4
l.new(tc.outputs["Object"], vn.inputs["Vector"])
vr = n.new("ShaderNodeMapRange"); vr.inputs["From Min"].default_value = 0.485; vr.inputs["From Max"].default_value = 0.5
vr2 = n.new("ShaderNodeMapRange"); vr2.inputs["From Min"].default_value = 0.515; vr2.inputs["From Max"].default_value = 0.5
l.new(vn.outputs["Fac"], vr.inputs["Value"]); l.new(vn.outputs["Fac"], vr2.inputs["Value"])
vmin = n.new("ShaderNodeMath"); vmin.operation = "MINIMUM"; l.new(vr.outputs[0], vmin.inputs[0]); l.new(vr2.outputs[0], vmin.inputs[1])
vmix = n.new("ShaderNodeMix"); vmix.data_type = "RGBA"
l.new(vmin.outputs[0], vmix.inputs["Factor"]); l.new(ramp.outputs[0], vmix.inputs["A"]); vmix.inputs["B"].default_value = (0.22, 0.02, 0.03, 1)
l.new(vmix.outputs["Result"], b.inputs["Base Color"])
b.subsurface_method = "BURLEY"
b.inputs["Subsurface Weight"].default_value = 0.9; b.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.3)
b.inputs["Subsurface Scale"].default_value = 0.0025
b.inputs["Roughness"].default_value = 0.42; b.inputs["Coat Weight"].default_value = 0.3; b.inputs["Coat Roughness"].default_value = 0.2
# fine tissue bump
fn = n.new("ShaderNodeTexNoise"); fn.inputs["Scale"].default_value = 260; fn.inputs["Detail"].default_value = 6
l.new(tc.outputs["Object"], fn.inputs["Vector"])
hsum = n.new("ShaderNodeMath"); hsum.operation = "MULTIPLY_ADD"; l.new(vmin.outputs[0], hsum.inputs[0]); hsum.inputs[1].default_value = 0.6
l.new(fn.outputs["Fac"], hsum.inputs[2])
bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.3; bp.inputs["Distance"].default_value = 0.0006
l.new(hsum.outputs[0], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
# neural activity: travelling thin wavefronts (4D noise contour lines) on gyral crowns, blue->violet
an = n.new("ShaderNodeTexNoise"); an.noise_dimensions = "4D"; an.inputs["Scale"].default_value = 9; an.inputs["Detail"].default_value = 1
l.new(tc.outputs["Object"], an.inputs["Vector"]); value_node_driver(an.inputs["W"], "frame/55")
band = n.new("ShaderNodeMath"); band.operation = "PINGPONG"; band.inputs[1].default_value = 0.06
l.new(an.outputs["Fac"], band.inputs[0])
bandr = n.new("ShaderNodeMapRange"); bandr.inputs["From Min"].default_value = 0.02; bandr.inputs["From Max"].default_value = 0.0
l.new(band.outputs[0], bandr.inputs["Value"])
gate = n.new("ShaderNodeTexNoise"); gate.noise_dimensions = "4D"; gate.inputs["Scale"].default_value = 3.5
l.new(tc.outputs["Object"], gate.inputs["Vector"]); value_node_driver(gate.inputs["W"], "frame/90+3.1")
gater = n.new("ShaderNodeMapRange"); gater.inputs["From Min"].default_value = 0.52; gater.inputs["From Max"].default_value = 0.66
l.new(gate.outputs["Fac"], gater.inputs["Value"])
crown = n.new("ShaderNodeMapRange"); crown.inputs["From Min"].default_value = 0.1; crown.inputs["From Max"].default_value = -0.4
l.new(attr.outputs["Fac"], crown.inputs["Value"])
e1 = n.new("ShaderNodeMath"); e1.operation = "MULTIPLY"; l.new(bandr.outputs[0], e1.inputs[0]); l.new(gater.outputs[0], e1.inputs[1])
e2 = n.new("ShaderNodeMath"); e2.operation = "MULTIPLY"; l.new(e1.outputs[0], e2.inputs[0]); l.new(crown.outputs[0], e2.inputs[1])
ints = n.new("ShaderNodeValue"); ints.name = "ActivityGain"; ints.outputs[0].default_value = 4.0
e3 = n.new("ShaderNodeMath"); e3.operation = "MULTIPLY"; l.new(e2.outputs[0], e3.inputs[0]); l.new(ints.outputs[0], e3.inputs[1])
ecol = n.new("ShaderNodeMix"); ecol.data_type = "RGBA"
l.new(gater.outputs[0], ecol.inputs["Factor"]); ecol.inputs["A"].default_value = (0.45, 0.35, 1.0, 1); ecol.inputs["B"].default_value = (0.25, 0.75, 1.0, 1)
l.new(ecol.outputs["Result"], b.inputs["Emission Color"]); l.new(e3.outputs[0], b.inputs["Emission Strength"])
for o in parts:
    assign(o, m)

# cerebellum / brainstem: folia via fine wave bands, slightly paler
m2 = m.copy(); m2.name = "Cerebellum"
n2, l2 = m2.node_tree.nodes, m2.node_tree.links
wv = n2.new("ShaderNodeTexWave"); wv.bands_direction = "Z"; wv.inputs["Scale"].default_value = 160; wv.inputs["Distortion"].default_value = 3
l2.new(n2["Texture Coordinate"].outputs["Object"], wv.inputs["Vector"])
l2.new(wv.outputs["Fac"], n2["Bump"].inputs["Height"]); n2["Bump"].inputs["Strength"].default_value = 0.5
n2["Bump"].inputs["Distance"].default_value = 0.0012
n2["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
for lk in list(l2):
    if lk.to_socket == n2["Principled BSDF"].inputs["Emission Strength"]:
        l2.remove(lk)
l2.new(n2["Color Ramp"].outputs[0], n2["Principled BSDF"].inputs["Base Color"])
n2["Attribute"].attribute_name = "none"
assign(cb, m2)

# ------------------------------------------------------------------ environment
w = s.world.node_tree; wn = w.nodes
grad = wn.new("ShaderNodeTexGradient"); grad.gradient_type = "SPHERICAL"
wr = wn.new("ShaderNodeValToRGB"); wr.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1); wr.color_ramp.elements[1].color = (0.004, 0.008, 0.022, 1)
wtc = wn.new("ShaderNodeTexCoord"); w.links.new(wtc.outputs["Generated"], grad.inputs[0])
w.links.new(grad.outputs[0], wr.inputs[0]); w.links.new(wr.outputs[0], wn["Background"].inputs[0])
# floating micro dust for depth (instanced tiny spheres, out of focus)
rng = np.random.default_rng(5)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.0005)
dust = bpy.context.object; dust.name = "dust"
dm = principled("Dust", (0.5, 0.7, 1.0), emission=(0.4, 0.6, 1.0), emission_strength=0.5); assign(dust, dm)
for i in range(70):
    d = dust.copy(); bpy.context.collection.objects.link(d)
    d.location = Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.6, 0.6), rng.uniform(-0.35, 0.35)))
    sc = rng.uniform(0.5, 2.0); d.scale = (sc, sc, sc)
dust.hide_render = True

light("AREA", "Key", (-0.55, -0.45, 0.6), 22, color=(0.75, 0.85, 1.0), size=0.6, target=(0, 0, 0))
light("AREA", "RimViolet", (0.6, 0.55, 0.25), 30, color=(0.55, 0.35, 1.0), size=0.5, target=(0, 0, 0))
light("AREA", "RimCyan", (-0.5, 0.6, -0.1), 10, color=(0.2, 0.75, 1.0), size=0.5, target=(0, 0, 0))
light("AREA", "Under", (0.0, -0.2, -0.6), 3, color=(0.5, 0.2, 0.25), size=0.8, target=(0, 0, 0))

# ------------------------------------------------------------------ camera: slow orbit, then controlled macro push-in
tgt = empty("CamTarget", (0, 0, 0.0))
cam = camera(lens=85, loc=(0, -0.95, 0.14), fstop=5.6, focus_obj=tgt)
track_to(cam, tgt)
# the brain turns slowly (lateral view of the left hemisphere), then settles while the camera dives in
for f, rz in [(1, 118), (112, 62), (156, 56)]:
    key(rig, "rotation_euler", f, Euler((0, 0, math.radians(rz))))
set_interp(rig, "BEZIER")
s.frame_set(156); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
o0 = Vector((0, -0.95, 0.14))
best = None
for ax_ in np.linspace(-0.05, 0.05, 11):
    for az_ in np.linspace(0.0, 0.05, 6):
        aim = Vector((ax_, 0.0, az_))
        dd = (aim - o0).normalized()
        hit, P_, N_, idx_, ob_, *_ = s.ray_cast(dg, o0, dd)
        if not hit or not ob_.name.startswith("cortex"):
            continue
        facing = abs(N_.dot(dd))
        score = facing - abs(ax_) * 2 - abs(az_ - 0.03) * 2
        if facing > 0.6 and (best is None or score > best[0]):
            best = (score, P_.copy(), ob_.name, facing)
_, P, obn, fac = best
print("dive point", P, obn, round(fac, 2), flush=True)
d = (P - o0).normalized()
for f, loc, t_, fs, lens in [(1, o0, Vector((0, 0, 0)), 5.6, 85), (100, o0 + d * 0.12, Vector((0, 0, 0.01)), 5.6, 85),
                             (130, P - d * 0.30, P + Vector((0, 0, -0.01)), 11.0, 85),
                             (156, P - d * 0.05 + Vector((0, 0, 0.006)), P, 32.0, 90)]:
    key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
    cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
for idb in (cam, tgt, cam.data):
    set_interp(idb, "BEZIER")
# activity rises toward the push-in
for f, v in [(1, 3.5), (90, 5.0), (156, 8.0)]:
    ints.outputs[0].default_value = v; ints.outputs[0].keyframe_insert("default_value", frame=f)
# gentle "breathing" of the brain (CSF pulsation ~ subtle)
for i in range(3):
    fc = rig.driver_add("scale", i); fc.driver.expression = "1+0.004*sin(frame*0.105)"

mode = ARGS[0] if ARGS else "still"
if mode == "still":
    os.makedirs("/tmp/claude-0/x/s2", exist_ok=True)
    for f in [int(a) for a in ARGS[1:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"/tmp/claude-0/x/s2/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, "renders/scene_renders/scene_02"), int(ARGS[1]), int(ARGS[2]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
