"""Scene 1A - bedroom: a person sleeping on their side, facing away from camera (frames 1-90).

The TotalSegmentator CT is defaced for privacy, so the face is never shown: the sleeper lies turned
away (hair, ear, nape in moonlight).  Camera dollies slowly toward the head; the comp then dissolves
"through the skin" into scene 1B (anatomy).
usage: python3 scene_01a.py -- still 1 45 90 | python3 scene_01a.py -- render 1 90
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import numpy as np
from mathutils.bvhtree import BVHTree
from scipy.ndimage import gaussian_filter, maximum_filter

ARGS = args()
s = reset(res=(720, 1280), samples=24)
s.cycles.adaptive_threshold = 0.04
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2
s.render.use_persistent_data = True
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1
H = A("human_anatomy")
M = 0.55
ROLL = math.radians(72)        # side-lying, face pointing away from camera (+X)

person = empty("Person", (0, 0, 0)); person.rotation_euler = (math.radians(-90), ROLL, 0)
skin = import_ply(f"{H}/skin.ply", "Skin"); skin.parent = person
bpy.context.view_layer.update()
co = np.empty(len(skin.data.vertices) * 3, np.float32); skin.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
mw = np.array(skin.matrix_world)
wco = co @ mw[:3, :3].T + mw[:3, 3]
head = co[:, 2] > 0.60
PILLOW_TOP = M + 0.15
person.location.z = PILLOW_TOP - 0.03 - wco[head, 2].min()
bpy.context.view_layer.update()
mw = np.array(skin.matrix_world); wco = co @ mw[:3, :3].T + mw[:3, 3]
HEAD_C = Vector(wco[head].mean(0))
print("head centre", HEAD_C, flush=True)

# ---- skin material (only ear / nape / a little cheek edge are visible)
m, n, l = mat("Skin")
b = n["Principled BSDF"]
tco = n.new("ShaderNodeTexCoord")
mott = n.new("ShaderNodeTexNoise"); mott.inputs["Scale"].default_value = 18; mott.inputs["Detail"].default_value = 8
l.new(tco.outputs["Object"], mott.inputs["Vector"])
cr = n.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].color = (0.46, 0.29, 0.23, 1); cr.color_ramp.elements[1].color = (0.62, 0.43, 0.35, 1)
l.new(mott.outputs["Fac"], cr.inputs[0]); l.new(cr.outputs[0], b.inputs["Base Color"])
b.subsurface_method = "BURLEY"
b.inputs["Subsurface Weight"].default_value = 1.0; b.inputs["Subsurface Radius"].default_value = (1.0, 0.38, 0.2)
b.inputs["Subsurface Scale"].default_value = 0.004; b.inputs["Roughness"].default_value = 0.48
b.inputs["Coat Weight"].default_value = 0.06; b.inputs["Coat Roughness"].default_value = 0.35
vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 1400; l.new(tco.outputs["Object"], vor.inputs["Vector"])
fine = n.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 420; l.new(tco.outputs["Object"], fine.inputs["Vector"])
hm = n.new("ShaderNodeMath"); hm.operation = "MULTIPLY_ADD"; l.new(vor.outputs["Distance"], hm.inputs[0]); hm.inputs[1].default_value = 0.6
l.new(fine.outputs["Fac"], hm.inputs[2])
bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.2; bump.inputs["Distance"].default_value = 0.0003
l.new(hm.outputs[0], bump.inputs["Height"]); l.new(bump.outputs[0], b.inputs["Normal"])
assign(skin, m)

# ---- hair: dense, swept back from the crown onto the pillow; covers the (defaced) face side too
x, y, z = co[:, 0], co[:, 1], co[:, 2]
vg = skin.vertex_groups.new(name="scalp")
scalp = ((z > 0.625) & (y > -0.03)) | ((z > 0.690) & (y > -0.09)) | (z > 0.765)
ear_gap = np.zeros_like(scalp)
w = np.where(scalp & ~ear_gap, 1.0, 0.0)
vg.add([int(i) for i in np.where(w > 0)[0]], 1.0, "REPLACE")
skin.modifiers.new("hair", "PARTICLE_SYSTEM")
psys = skin.particle_systems[0]; ps = psys.settings; psys.vertex_group_density = "scalp"
ps.type = "HAIR"; ps.count = 12000; ps.hair_length = 0.15; ps.emit_from = "FACE"; ps.use_emit_random = True
ps.use_advanced_hair = True; ps.normal_factor = 0.006; ps.object_align_factor = (0, 0.004, 0.022)
ps.child_type = "INTERPOLATED"; ps.rendered_child_count = 12; ps.child_parting_factor = 0.4
ps.clump_factor = 0.12; ps.clump_shape = 0.0; ps.child_radius = 0.025
ps.roughness_1 = 0.010; ps.roughness_1_size = 0.4; ps.roughness_2 = 0.03; ps.roughness_2_threshold = 0.7
ps.roughness_endpoint = 0.012; ps.child_length = 0.85; ps.child_length_threshold = 0.4
ps.kink = "WAVE"; ps.kink_amplitude = 0.006; ps.kink_frequency = 1.2; ps.kink_shape = 0.3
ps.root_radius = 1.0; ps.tip_radius = 0.15; ps.radius_scale = 0.000055
ps.display_step = 3; ps.render_step = 5; ps.hair_step = 8; ps.use_hair_bspline = True
hair_m, hn, hl = mat("Hair"); hn.remove(hn["Principled BSDF"])
hb = hn.new("ShaderNodeBsdfHairPrincipled"); hb.parametrization = "MELANIN"
hb.inputs["Melanin"].default_value = 0.72; hb.inputs["Melanin Redness"].default_value = 0.45
hb.inputs["Roughness"].default_value = 0.32; hb.inputs["Radial Roughness"].default_value = 0.35
hb.inputs["Random Color"].default_value = 0.15; hb.inputs["Random Roughness"].default_value = 0.2
hl.new(hb.outputs[0], hn["Material Output"].inputs["Surface"])
skin.data.materials.append(hair_m); ps.material_slot = "Hair"


# ---- bedroom
def box(name, loc, size, bevel=0.0, sub=0):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2); bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bv = o.modifiers.new("bev", "BEVEL"); bv.width = bevel; bv.segments = 4
    if sub:
        ss = o.modifiers.new("sub", "SUBSURF"); ss.levels = ss.render_levels = sub
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def fabric(name, color, sheen=1.0, rough=0.92, weave=900):
    m, n, l = mat(name); b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = sheen; b.inputs["Sheen Roughness"].default_value = 0.4
    tc = n.new("ShaderNodeTexCoord")
    w1 = n.new("ShaderNodeTexWave"); w1.inputs["Scale"].default_value = weave; w1.inputs["Distortion"].default_value = 2
    w2 = n.new("ShaderNodeTexWave"); w2.bands_direction = "Y"; w2.inputs["Scale"].default_value = weave
    l.new(tc.outputs["Object"], w1.inputs["Vector"]); l.new(tc.outputs["Object"], w2.inputs["Vector"])
    mx = n.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; l.new(w1.outputs["Fac"], mx.inputs[0]); l.new(w2.outputs["Fac"], mx.inputs[1])
    cn = n.new("ShaderNodeTexNoise"); cn.inputs["Scale"].default_value = 6; l.new(tc.outputs["Object"], cn.inputs["Vector"])
    hs = n.new("ShaderNodeMath"); hs.operation = "MULTIPLY_ADD"; l.new(cn.outputs["Fac"], hs.inputs[0]); hs.inputs[1].default_value = 3.0
    l.new(mx.outputs[0], hs.inputs[2])
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.3; bp.inputs["Distance"].default_value = 0.0008
    l.new(hs.outputs[0], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
    return m


bed_frame = box("BedFrame", (0, -0.18, 0.22), (1.86, 2.36, 0.30), bevel=0.02)
assign(bed_frame, principled("Walnut", (0.05, 0.03, 0.02), rough=0.35, coat=0.3))
mattress = box("Mattress", (0, -0.18, M - 0.11), (1.70, 2.20, 0.22), bevel=0.05, sub=1)
assign(mattress, fabric("Sheet", (0.40, 0.42, 0.46)))
headboard = box("Headboard", (0, 1.02, 0.85), (1.95, 0.10, 1.10), bevel=0.04, sub=1)
assign(headboard, fabric("Headboard", (0.03, 0.035, 0.05), weave=300))
wall = box("Wall", (0, 1.12, 1.6), (8, 0.05, 3.2)); assign(wall, principled("Plaster", (0.018, 0.02, 0.028), rough=0.9))
floor = box("Floor", (0, 0, -0.005), (8, 8, 0.01)); assign(floor, principled("FloorWood", (0.03, 0.018, 0.012), rough=0.3))
stand = box("Nightstand", (1.25, 0.80, 0.28), (0.5, 0.42, 0.56), bevel=0.01)
assign(stand, principled("WalnutStand", (0.045, 0.028, 0.018), rough=0.4, coat=0.3))
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.30, location=(1.27, 0.88, 0.80), vertices=64)
assign(bpy.context.object, principled("LampShade", (0.5, 0.45, 0.38), rough=0.8, emission=(1.0, 0.55, 0.25), emission_strength=1.4))
bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.11, location=(1.13, 0.70, 0.615), vertices=48)
assign(bpy.context.object, principled("GlassWater", (0.85, 0.9, 0.95), rough=0.02, transmission=1.0, ior=1.33))
book = box("Book", (1.30, 0.72, 0.575), (0.22, 0.15, 0.03), bevel=0.003); assign(book, principled("BookCover", (0.08, 0.12, 0.2), rough=0.6))

pil = box("Pillow", (0.02, 0.74, M + 0.075), (0.70, 0.46, 0.18), bevel=0.085, sub=3)
dsp = pil.modifiers.new("lump", "DISPLACE"); tx = bpy.data.textures.new("lump", "CLOUDS"); tx.noise_scale = 0.12; dsp.texture = tx; dsp.strength = 0.035
assign(pil, fabric("Pillowcase", (0.50, 0.52, 0.57)))
pil2 = box("Pillow2", (0.62, 0.80, M + 0.07), (0.62, 0.42, 0.16), bevel=0.07, sub=2)
pil2.rotation_euler = (0.05, -0.08, 0.06)
d2 = pil2.modifiers.new("lump", "DISPLACE"); d2.texture = tx; d2.strength = 0.02
assign(pil2, fabric("Pillowcase2", (0.50, 0.52, 0.57)))

# ---- duvet heightfield over the side-lying body
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
sk_eval = skin.evaluated_get(dg)
bvh = BVHTree.FromObject(sk_eval, dg, deform=False)
mwi = skin.matrix_world.inverted()
nx, ny = 170, 200
xs = np.linspace(-1.0, 1.0, nx); ys = np.linspace(-1.42, 0.60, ny)
Hh = np.full((ny, nx), M + 0.02)
dl = (mwi.to_3x3() @ Vector((0, 0, -1))).normalized()
for j, yy in enumerate(ys):
    for i, xx in enumerate(xs):
        if abs(xx) < 0.5 and yy > -0.05:
            hit = bvh.ray_cast(mwi @ Vector((xx, yy, 2.0)), dl)
            if hit[0] is not None:
                Hh[j, i] = max(Hh[j, i], (skin.matrix_world @ hit[0]).z + 0.045)
        if yy <= 0.1:   # bent legs (side-lying sleeper), CT stops at the thighs
            for lx, lz in ((0.02, 0.24), (0.10, 0.17)):
                r = 0.09 - 0.03 * np.clip(-yy / 1.1, 0, 1)
                cx = lx - 0.25 * np.clip(-yy / 0.6, 0, 1) * np.clip((yy + 1.3) / 0.7, 0, 1)
                dx = (xx - cx) / r
                if abs(dx) < 1 and yy > -1.05:
                    Hh[j, i] = max(Hh[j, i], M + 0.02 + lz * math.sqrt(1 - dx * dx))
Hh = maximum_filter(Hh, size=(5, 9)); Hh = gaussian_filter(Hh, (2.4, 2.4))
XX, YY = np.meshgrid(xs, ys)
Hh -= np.clip(np.abs(XX) - 0.86, 0, None) * 3.2 + np.clip(-1.27 - YY, 0, None) * 3.0
rng = np.random.default_rng(3)
Hh += (gaussian_filter(rng.standard_normal(Hh.shape), 3.0) * 0.07 + gaussian_filter(rng.standard_normal(Hh.shape), 1.2) * 0.012) * np.clip((Hh - M) * 8, 0.2, 1)
Hh[-7:, :] += np.linspace(0, 0.014, 7)[:, None]
mesh = bpy.data.meshes.new("Duvet")
mesh.from_pydata([(float(XX[j, i]), float(YY[j, i]), float(Hh[j, i])) for j in range(ny) for i in range(nx)], [],
                 [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(ny - 1) for i in range(nx - 1)])
duvet = bpy.data.objects.new("Duvet", mesh); bpy.context.collection.objects.link(duvet)
for p in duvet.data.polygons:
    p.use_smooth = True
so = duvet.modifiers.new("sol", "SOLIDIFY"); so.thickness = 0.03; so.offset = -1
ss = duvet.modifiers.new("sub", "SUBSURF"); ss.levels = ss.render_levels = 1
dm_ = fabric("Duvet", (0.22, 0.25, 0.31), weave=700)
_n, _l = dm_.node_tree.nodes, dm_.node_tree.links
q = _n.new("ShaderNodeTexWave"); q.bands_direction = "Y"; q.wave_profile = "SIN"; q.inputs["Scale"].default_value = 3.2
q.inputs["Distortion"].default_value = 0.4
_l.new(_n["Texture Coordinate"].outputs["Object"], q.inputs["Vector"])
qp = _n.new("ShaderNodeMath"); qp.operation = "POWER"; _l.new(q.outputs["Fac"], qp.inputs[0]); qp.inputs[1].default_value = 0.25
qa = _n.new("ShaderNodeMath"); qa.operation = "MULTIPLY_ADD"; _l.new(qp.outputs[0], qa.inputs[0]); qa.inputs[1].default_value = 6.0
_l.new(_n["Math.001"].outputs[0], qa.inputs[2])
_l.new(qa.outputs[0], _n["Bump"].inputs["Height"]); _n["Bump"].inputs["Distance"].default_value = 0.006
assign(duvet, dm_)
duvet.shape_key_add(name="Basis"); kb = duvet.shape_key_add(name="inhale")
for v in kb.data:
    c = v.co
    wgt = math.exp(-(((c.x + 0.05) / 0.22) ** 2) - ((c.y - 0.38) / 0.18) ** 2)
    c.z += 0.013 * wgt
fc = kb.driver_add("value"); fc.driver.expression = "0.5+0.5*sin(frame*0.0524)"
pz0 = person.location.z
fcp = person.driver_add("location", 2); fcp.driver.expression = f"{pz0}+0.0012*sin(frame*0.0524)"

# ---- lighting: moonlight through a window behind the camera (window-frame shadows), cool rim, faint warm bounce
moon = light("SPOT", "Moon", (-3.0, -0.3, 2.4), 520, color=(0.55, 0.68, 1.0), size=0.05, target=(0.1, 0.45, M + 0.1), spot=math.radians(26))
for nm, loc, sz in [("MullV", (-2.0, -0.25, 1.75), (0.05, 0.05, 1.6)), ("MullH", (-2.0, -0.25, 1.80), (0.05, 1.6, 0.05)),
                    ("FrameT", (-2.0, -0.25, 2.55), (0.08, 1.7, 0.1)), ("FrameB", (-2.0, -0.25, 1.0), (0.08, 1.7, 0.1)),
                    ("FrameL", (-2.0, -1.05, 1.75), (0.08, 0.1, 1.7)), ("FrameR", (-2.0, 0.55, 1.75), (0.08, 0.1, 1.7))]:
    o = box(nm, loc, sz); assign(o, principled("Black", (0.01, 0.01, 0.01))); o.visible_camera = False
light("AREA", "Rim", (0.7, 1.25, 1.25), 30, color=(0.35, 0.6, 1.0), size=0.4, target=HEAD_C)
light("AREA", "Fill", (-1.6, -1.2, 1.2), 0.35, color=(0.3, 0.4, 0.75), size=2.0, target=(0, 0.4, M))
light("POINT", "Warm", (1.27, 0.88, 0.80), 9, color=(1.0, 0.5, 0.22), size=0.08)

# ---- camera: slow dolly from a medium shot to the back of the head / nape
tgt = empty("CamTarget", HEAD_C)
cam = camera(lens=45, loc=(-0.95, 0.05, 1.20), fstop=2.2, focus_obj=tgt); track_to(cam, tgt)
NAPE = HEAD_C + Vector((-0.07, -0.06, -0.01))
s.render.motion_blur_shutter = 0.25
SHOULDER = Vector((HEAD_C.x - 0.10, HEAD_C.y - 0.26, HEAD_C.z - 0.02))
for f, loc, t_, lens, fs in [(1, (-0.70, -0.30, M + 0.42), SHOULDER + Vector((0.0, 0.05, 0.0)), 40, 2.0),
                              (64, (-0.42, 0.02, M + 0.33), SHOULDER + Vector((0.02, 0.14, 0.03)), 45, 1.8)]:
    key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
    cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
for idb in (cam, tgt, cam.data):
    set_interp(idb, "BEZIER")

mode = ARGS[0] if ARGS else "still"
if mode == "still":
    os.makedirs("/tmp/claude-0/x/s1a", exist_ok=True)
    for f in [int(a) for a in ARGS[1:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"/tmp/claude-0/x/s1a/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, "renders/scene_renders/scene_01a"), int(ARGS[1]), int(ARGS[2]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
