"""Scene 4 - THE BODY REPAIRS ITSELF (6 s + handle = 186 frames).

Units: 1 BU = 100 um.  Arteriole (radius 25 um) with biconcave red blood cells (Evans-Fung profile,
R = 3.9 um), a few leukocytes and platelets in pulsatile flow at a sleeping heart rate (~58 bpm).
The camera tracks the flow, then passes through the vessel wall into skeletal muscle: fibres
(~50 um) with sarcomere striations, capillaries running parallel to the fibres with RBCs in single
file, and hormone molecules (e.g. growth hormone, released mainly in deep sleep) diffusing from the
capillaries and binding at the fibre surface - a restrained visualisation of overnight maintenance.
usage: python3 scene_04.py -- still 1 90 160 | python3 scene_04.py -- render 1 186
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import numpy as np

ARGS = args()
s = reset(res=(720, 1280), samples=22)
s.cycles.adaptive_threshold = 0.05
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2; s.cycles.transparent_max_bounces = 10
s.render.use_persistent_data = True
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1
s.render.motion_blur_shutter = 0.15
rng = np.random.default_rng(7)
FOG = (0.035, 0.004, 0.006)
s.world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.006, 0.02, 1)
R_ART = 0.25
BPM = 58.0


def fogwrap(m, density=0.9, color=FOG):
    n, l = m.node_tree.nodes, m.node_tree.links
    out = n["Material Output"]; src = out.inputs["Surface"].links[0].from_socket
    cd = n.new("ShaderNodeCameraData")
    ex = n.new("ShaderNodeMath"); ex.operation = "MULTIPLY"; l.new(cd.outputs["View Distance"], ex.inputs[0]); ex.inputs[1].default_value = -density
    e2 = n.new("ShaderNodeMath"); e2.operation = "EXPONENT"; l.new(ex.outputs[0], e2.inputs[0])
    fac = n.new("ShaderNodeMath"); fac.operation = "SUBTRACT"; fac.inputs[0].default_value = 1.0; l.new(e2.outputs[0], fac.inputs[1])
    em = n.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1)
    mx = n.new("ShaderNodeMixShader"); l.new(fac.outputs[0], mx.inputs[0]); l.new(src, mx.inputs[1]); l.new(em.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])
    return m


def near_fade(m, d0=0.03, d1=0.09):
    """surfaces closer than d1 to the camera fade out (lets the camera pass through the wall cleanly)."""
    n, l = m.node_tree.nodes, m.node_tree.links
    out = n["Material Output"]; src = out.inputs["Surface"].links[0].from_socket
    cd = n.new("ShaderNodeCameraData")
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = d0; mr.inputs["From Max"].default_value = d1
    mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
    l.new(cd.outputs["View Distance"], mr.inputs["Value"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader"); l.new(mr.outputs[0], mx.inputs[0]); l.new(src, mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])


# ------------------------------------------------------------------ geometry builders
def revolve(profile_r, profile_z, segs=32):
    V, F = [], []
    nr = len(profile_r)
    for j in range(segs):
        a = 2 * np.pi * j / segs
        for i in range(nr):
            V.append((profile_r[i] * np.cos(a), profile_r[i] * np.sin(a), profile_z[i]))
    for j in range(segs):
        j2 = (j + 1) % segs
        for i in range(nr - 1):
            F.append((j * nr + i, j * nr + i + 1, j2 * nr + i + 1, j2 * nr + i))
    return np.array(V), F


def rbc_geom(R=0.039):
    # Evans & Fung (1972) biconcave profile, closed loop: top surface r 0->R, bottom R->0
    x = np.sin(np.linspace(0, np.pi / 2, 14)); x[-1] = 0.9999
    zz = 0.5 * np.sqrt(1 - x ** 2) * (0.81 + 7.83 * x ** 2 - 4.39 * x ** 4) / 3.91 * R
    r = np.concatenate([x, x[::-1][1:]]) * R
    z = np.concatenate([zz, -zz[::-1][1:]])
    return revolve(r, z, 24)


def tube(path, radius, segs=48):
    n = len(path)
    t = np.gradient(path, axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True)
    a = np.cross(t[0], [0.3, 0.1, 0.95]); a /= np.linalg.norm(a)
    V, F = [], []
    ang = np.linspace(0, 2 * np.pi, segs, endpoint=False)
    for i in range(n):
        a = a - t[i] * np.dot(a, t[i]); a /= np.linalg.norm(a); b = np.cross(t[i], a)
        V.extend(path[i] + radius * (np.outer(np.cos(ang), a) + np.outer(np.sin(ang), b)))
    for i in range(n - 1):
        for j in range(segs):
            F.append((i * segs + j, i * segs + (j + 1) % segs, (i + 1) * segs + (j + 1) % segs, (i + 1) * segs + j))
    return np.array(V), F


def mesh_obj(name, V, F, smooth=True):
    me = bpy.data.meshes.new(name); me.from_pydata(np.asarray(V).tolist(), [], F); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return o


def rot_matrices(axes, angles):
    axes = axes / np.linalg.norm(axes, axis=1, keepdims=True)
    c, s_ = np.cos(angles)[:, None, None], np.sin(angles)[:, None, None]
    x, y, z = axes[:, 0, None, None], axes[:, 1, None, None], axes[:, 2, None, None]
    K = np.concatenate([np.concatenate([0 * x, -z, y], 2), np.concatenate([z, 0 * x, -x], 2), np.concatenate([-y, x, 0 * x], 2)], 1)
    I = np.eye(3)[None]
    return I + s_ * K + (1 - c) * (K @ K)


# ------------------------------------------------------------------ arteriole interior
Y0, Y1 = -2.0, 14.0
art_path = np.stack([0.03 * np.sin(np.linspace(Y0, Y1, 200) * 0.6), np.linspace(Y0, Y1, 200), 0.02 * np.cos(np.linspace(Y0, Y1, 200) * 0.45)], 1)
V, F = tube(art_path, R_ART, 72)
wall = mesh_obj("ArterioleWall", V, F)
so = wall.modifiers.new("sol", "SOLIDIFY"); so.thickness = 0.03; so.offset = 1
mwall, n, l = mat("Endothelium")
b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
tc = n.new("ShaderNodeTexCoord")
mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (5.0, 1.2, 5.0)    # endothelial cells elongated along flow
l.new(tc.outputs["Object"], mp.inputs[0])
vo = n.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 7; l.new(mp.outputs[0], vo.inputs["Vector"])
ve = n.new("ShaderNodeTexVoronoi"); ve.feature = "DISTANCE_TO_EDGE"; ve.inputs["Scale"].default_value = 7; l.new(mp.outputs[0], ve.inputs["Vector"])
cr = n.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.42, 0.04, 0.05, 1); cr.color_ramp.elements[1].color = (0.70, 0.16, 0.16, 1)
l.new(vo.outputs["Distance"], cr.inputs[0]); l.new(cr.outputs[0], b.inputs["Base Color"])
b.inputs["Subsurface Weight"].default_value = 1.0; b.inputs["Subsurface Radius"].default_value = (1.0, 0.2, 0.15)
b.inputs["Subsurface Scale"].default_value = 0.06; b.inputs["Roughness"].default_value = 0.25
b.inputs["Coat Weight"].default_value = 1.0; b.inputs["Coat Roughness"].default_value = 0.08
nuc = n.new("ShaderNodeMapRange"); nuc.inputs["From Min"].default_value = 0.12; nuc.inputs["From Max"].default_value = 0.0
l.new(vo.outputs["Distance"], nuc.inputs["Value"])
edg = n.new("ShaderNodeMapRange"); edg.inputs["From Min"].default_value = 0.0; edg.inputs["From Max"].default_value = 0.05
edg.inputs["To Min"].default_value = -1.0; edg.inputs["To Max"].default_value = 0.0
l.new(ve.outputs["Distance"], edg.inputs["Value"])
hs = n.new("ShaderNodeMath"); hs.operation = "ADD"; l.new(nuc.outputs[0], hs.inputs[0]); l.new(edg.outputs[0], hs.inputs[1])
bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5; bp.inputs["Distance"].default_value = 0.01
l.new(hs.outputs[0], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
fogwrap(mwall, 0.8); near_fade(mwall); assign(wall, mwall)

# RBCs
rv, rf = rbc_geom()
NR = 340
rbc_y0 = rng.uniform(Y0, Y1, NR)
rbc_r = np.sqrt(rng.uniform(0, 1, NR)) * (R_ART - 0.06)
rbc_a = rng.uniform(0, 2 * np.pi, NR)
rbc_axis = rng.normal(0, 1, (NR, 3)); rbc_spin = rng.uniform(-0.06, 0.06, NR); rbc_ph = rng.uniform(0, 6.28, NR)
NV = len(rv)
rbc_obj = mesh_obj("RBCs", np.tile(rv, (NR, 1)), [tuple(i + k * NV for i in f) for k in range(NR) for f in rf])
mr_, n, l = mat("RBC")
b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
b.inputs["Base Color"].default_value = (0.55, 0.02, 0.025, 1); b.inputs["Subsurface Weight"].default_value = 1.0
b.inputs["Subsurface Radius"].default_value = (1.0, 0.1, 0.08); b.inputs["Subsurface Scale"].default_value = 0.03
b.inputs["Roughness"].default_value = 0.3; b.inputs["Coat Weight"].default_value = 0.6; b.inputs["Coat Roughness"].default_value = 0.15
fogwrap(mr_, 0.8); near_fade(mr_, 0.01, 0.04); assign(rbc_obj, mr_)


def flow_disp(f, rr):
    """axial displacement at frame f for radial position rr: Poiseuille profile x pulsatile flow."""
    tt = f / 30.0
    w = 2 * np.pi * BPM / 60
    base = 0.55 * tt + 0.12 * (np.sin(w * tt) / w)          # mean + systolic surge integral
    return base * (1 - 0.65 * (rr / R_ART) ** 2)


def rbc_update(f):
    d = flow_disp(f, rbc_r)
    y = (rbc_y0 + d - Y0) % (Y1 - Y0) + Y0
    a = rbc_a + 0.01 * np.sin(f * 0.05 + rbc_ph)
    cx = 0.03 * np.sin(y * 0.6) + rbc_r * np.cos(a); cz = 0.02 * np.cos(y * 0.45) + rbc_r * np.sin(a)
    Rm = rot_matrices(rbc_axis, rbc_ph + rbc_spin * f)
    P = np.einsum("nij,vj->nvi", Rm, rv) + np.stack([cx, y, cz], 1)[:, None, :]
    rbc_obj.data.vertices.foreach_set("co", P.astype(np.float32).ravel()); rbc_obj.data.update()


# leukocytes (few, bumpy spheres) and platelets (small discs)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.055)
wbc = bpy.context.object; wbc.name = "WBC0"
for p in wbc.data.polygons:
    p.use_smooth = True
wd = wbc.modifiers.new("d", "DISPLACE"); wt = bpy.data.textures.new("wt", "VORONOI"); wt.noise_scale = 0.012; wd.texture = wt; wd.strength = 0.012
mwbc = principled("Leukocyte", (0.75, 0.72, 0.68), rough=0.5, sss=1.0, sss_radius=(1, 0.8, 0.7), sss_scale=0.05)
fogwrap(mwbc, 0.8); near_fade(mwbc, 0.01, 0.05); assign(wbc, mwbc)
wbcs = [wbc]
for i in range(3):
    o = wbc.copy(); bpy.context.collection.objects.link(o); wbcs.append(o)
wbc_par = [(rng.uniform(Y0 + 2, Y1 - 2), rng.uniform(0.08, 0.17), rng.uniform(0, 6.3)) for _ in wbcs]


def wbc_update(f):
    for o, (y0, rr, a) in zip(wbcs, wbc_par):
        y = (y0 + flow_disp(f, rr) * 0.8 - Y0) % (Y1 - Y0) + Y0
        o.location = (0.03 * np.sin(y * 0.6) + rr * np.cos(a), y, rr * np.sin(a))
        o.rotation_euler = (f * 0.01, 0, f * 0.013)


# ------------------------------------------------------------------ muscle compartment (outside the wall, +X side)
MX = 0.95     # centre of the muscle field in x
fibres = []
k = 0
for i in range(-3, 5):
    for j in range(-3, 4):
        cx = MX + i * 0.52 + (j % 2) * 0.26 + rng.normal(0, 0.03); cz = j * 0.45 + rng.normal(0, 0.03)
        if cx < R_ART + 0.35:
            continue
        r = rng.uniform(0.2, 0.25)
        pth = np.stack([cx + 0.03 * np.sin(np.linspace(Y0, Y1, 120) * 0.4 + k), np.linspace(Y0, Y1, 120), cz + 0.03 * np.cos(np.linspace(Y0, Y1, 120) * 0.3 + k)], 1)
        V, F = tube(pth, r, 40)
        fibres.append(mesh_obj(f"Fibre{k}", V, F)); k += 1
mf, n, l = mat("MuscleFibre")
b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
tc = n.new("ShaderNodeTexCoord")
wv = n.new("ShaderNodeTexWave"); wv.bands_direction = "Y"; wv.inputs["Scale"].default_value = 18; wv.inputs["Distortion"].default_value = 0.6
wv.inputs["Detail"].default_value = 1
l.new(tc.outputs["Object"], wv.inputs["Vector"])                       # sarcomere striations (A/I bands)
mf2 = n.new("ShaderNodeMapping"); mf2.inputs["Scale"].default_value = (40, 1, 40); l.new(tc.outputs["Object"], mf2.inputs[0])
fn = n.new("ShaderNodeTexNoise"); fn.inputs["Scale"].default_value = 6; l.new(mf2.outputs[0], fn.inputs["Vector"])   # myofibril lines
cr = n.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0.30, 0.03, 0.04, 1); cr.color_ramp.elements[1].color = (0.58, 0.12, 0.12, 1)
l.new(wv.outputs["Fac"], cr.inputs[0]); l.new(cr.outputs[0], b.inputs["Base Color"])
hsum = n.new("ShaderNodeMath"); hsum.operation = "MULTIPLY_ADD"; l.new(wv.outputs["Fac"], hsum.inputs[0]); hsum.inputs[1].default_value = 0.7; l.new(fn.outputs["Fac"], hsum.inputs[2])
bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; bp.inputs["Distance"].default_value = 0.004
l.new(hsum.outputs[0], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
b.inputs["Subsurface Weight"].default_value = 1.0; b.inputs["Subsurface Radius"].default_value = (1.0, 0.2, 0.15)
b.inputs["Subsurface Scale"].default_value = 0.08; b.inputs["Roughness"].default_value = 0.3; b.inputs["Coat Weight"].default_value = 0.7
# receptor activation: soft cyan glints that pulse where hormone binds (restrained)
rv_ = n.new("ShaderNodeTexVoronoi"); rv_.voronoi_dimensions = "4D"; rv_.inputs["Scale"].default_value = 14
l.new(tc.outputs["Object"], rv_.inputs["Vector"]); value_node_driver(rv_.inputs["W"], "frame/40")
rr_ = n.new("ShaderNodeMapRange"); rr_.inputs["From Min"].default_value = 0.08; rr_.inputs["From Max"].default_value = 0.0
l.new(rv_.outputs["Distance"], rr_.inputs["Value"])
gate = n.new("ShaderNodeMath"); gate.operation = "GREATER_THAN"; l.new(rv_.outputs["Color"], gate.inputs[0]); gate.inputs[1].default_value = 0.8
eg = n.new("ShaderNodeMath"); eg.operation = "MULTIPLY"; l.new(rr_.outputs[0], eg.inputs[0]); l.new(gate.outputs[0], eg.inputs[1])
rgain = n.new("ShaderNodeValue"); rgain.name = "RepairGain"; rgain.outputs[0].default_value = 0.0
eg2 = n.new("ShaderNodeMath"); eg2.operation = "MULTIPLY"; l.new(eg.outputs[0], eg2.inputs[0]); l.new(rgain.outputs[0], eg2.inputs[1])
b.inputs["Emission Color"].default_value = (0.35, 0.85, 1.0, 1); l.new(eg2.outputs[0], b.inputs["Emission Strength"])
fogwrap(mf, 0.55, color=(0.02, 0.006, 0.012)); near_fade(mf, 0.02, 0.06)
for o in fibres:
    assign(o, mf)
for fval, g in [(1, 0.0), (120, 0.0), (150, 2.5), (186, 3.0)]:
    rgain.outputs[0].default_value = g; rgain.outputs[0].keyframe_insert("default_value", frame=fval)

# capillaries between fibres, RBCs in single file
caps = []
cap_paths = []
for (cx, cz) in [(MX + 0.0, 0.23), (MX + 0.52, -0.22), (MX + 0.26, 0.68), (MX + 0.78, 0.23), (MX - 0.26, -0.22)]:
    pth = np.stack([np.full(160, cx) + 0.02 * np.sin(np.linspace(Y0, Y1, 160)), np.linspace(Y0, Y1, 160), np.full(160, cz)], 1)
    V, F = tube(pth, 0.045, 24); caps.append(mesh_obj("Capillary", V, F)); cap_paths.append((cx, cz))
mcap = principled("CapWall", (0.75, 0.3, 0.3), rough=0.15, alpha=1.0, sss=0.3)
nn, ll = mcap.node_tree.nodes, mcap.node_tree.links
trc = nn.new("ShaderNodeBsdfTransparent"); mxc = nn.new("ShaderNodeMixShader"); mxc.inputs[0].default_value = 0.6
ll.new(nn["Principled BSDF"].outputs[0], mxc.inputs[1]); ll.new(trc.outputs[0], mxc.inputs[2]); ll.new(mxc.outputs[0], nn["Material Output"].inputs["Surface"])
fogwrap(mcap, 0.55, color=(0.02, 0.006, 0.012))
for o in caps:
    assign(o, mcap)
NCR = 30
crv, crf = rbc_geom(0.034)
cap_cells = mesh_obj("CapRBCs", np.tile(crv, (NCR * len(cap_paths), 1)), [tuple(i + k * len(crv) for i in f) for k in range(NCR * len(cap_paths)) for f in crf])
assign(cap_cells, mr_)
cc_y = rng.uniform(Y0, Y1, (len(cap_paths), NCR)); cc_ax = rng.normal(0, 0.2, (len(cap_paths) * NCR, 3)) + [0, 1, 0]


def cap_update(f):
    allp = []
    Rm = rot_matrices(cc_ax, np.full(len(cc_ax), 1.2))
    for ci, (cx, cz) in enumerate(cap_paths):
        y = (cc_y[ci] + flow_disp(f, 0.0) * 0.5 - Y0) % (Y1 - Y0) + Y0
        allp.append(np.stack([np.full(NCR, cx) + 0.02 * np.sin(y), y, np.full(NCR, cz)], 1))
    allp = np.concatenate(allp)
    P = np.einsum("nij,vj->nvi", Rm, crv) + allp[:, None, :]
    cap_cells.data.vertices.foreach_set("co", P.astype(np.float32).ravel()); cap_cells.data.update()


# hormone molecules diffusing out of capillaries toward fibres
NH = 160
h_cap = rng.integers(0, len(cap_paths), NH); h_y = rng.uniform(1.0, 9.0, NH); h_dir = rng.normal(0, 1, (NH, 3)); h_dir[:, 1] *= 0.2
h_dir /= np.linalg.norm(h_dir, axis=1, keepdims=True); h_t0 = rng.uniform(80, 170, NH)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.008)
hp = bpy.context.object; hv = np.array([v.co[:] for v in hp.data.vertices]); hf = [tuple(p.vertices) for p in hp.data.polygons]; bpy.data.objects.remove(hp)
horm = mesh_obj("Hormones", np.tile(hv, (NH, 1)), [tuple(i + k * len(hv) for i in f) for k in range(NH) for f in hf])
mh = principled("Hormone", (1.0, 0.7, 0.3), rough=0.2, emission=(1.0, 0.62, 0.25), emission_strength=2.2)
fogwrap(mh, 0.55, color=(0.02, 0.006, 0.012)); assign(horm, mh)
horm.visible_shadow = False


def horm_update(f):
    tt = np.clip(f - h_t0, 0, None)
    dist = 0.05 + 0.22 * (1 - np.exp(-tt / 40.0))
    base = np.array([[cap_paths[c][0], 0, cap_paths[c][1]] for c in h_cap])
    p = base + h_dir * dist[:, None]; p[:, 1] = h_y + 0.0008 * tt
    p += 0.01 * np.stack([np.sin(f * 0.21 + np.arange(NH)), np.cos(f * 0.17 + np.arange(NH)), np.sin(f * 0.13 + 2 * np.arange(NH))], 1)
    p[tt <= 0] = [0, -50, 0]
    P = np.repeat(p, len(hv), axis=0) + np.tile(hv, (NH, 1))
    horm.data.vertices.foreach_set("co", P.astype(np.float32).ravel()); horm.data.update()


def update(scene, depsgraph=None):
    f = scene.frame_current + scene.frame_subframe
    rbc_update(f); wbc_update(f); cap_update(f); horm_update(f)


bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(update)

# ------------------------------------------------------------------ lights
light("AREA", "OutsideRed", (0.6, 4.0, 1.2), 200, color=(1.0, 0.25, 0.2), size=4, target=(0, 4.0, 0))
light("AREA", "OutsideBlue", (-1.2, 6.0, -0.8), 160, color=(0.25, 0.4, 1.0), size=4, target=(0, 5.0, 0))
light("AREA", "MuscleKey", (MX + 0.6, 7.5, 1.6), 140, color=(0.75, 0.8, 1.0), size=3, target=(MX, 6.0, 0))
light("AREA", "MuscleRim", (MX + 2.0, 9.0, -1.0), 120, color=(0.4, 0.45, 1.0), size=3, target=(MX, 6.0, 0))

# ------------------------------------------------------------------ camera
tgt = empty("CamTarget", (0, 2, 0))
cam = camera(lens=24, loc=(0, -1.2, 0), fstop=2.8, focus_obj=tgt); track_to(cam, tgt)
cam.data.clip_start = 0.003
camlight = light("POINT", "CamLight", (0, 0, 0), 2.5, color=(1.0, 0.8, 0.75), size=0.08); camlight.parent = cam
for yy in np.linspace(-1.0, 4.0, 6):
    light("POINT", f"Lumen{yy:.1f}", (0.12 * math.cos(yy * 2.1), yy, 0.12 * math.sin(yy * 2.1)), 1.6, color=(1.0, 0.55, 0.45), size=0.05)
camlight.location = (0.03, 0.04, 0.0)
path = [(1, (0.02, -1.0, 0.05), (0.0, 0.8, 0.0), 24, 18),
        (70, (0.0, 1.0, -0.02), (0.04, 2.8, 0.0), 24, 18),
        (108, (0.08, 2.4, 0.0), (0.30, 3.8, 0.05), 26, 18),
        (132, (0.30, 3.05, 0.12), (0.60, 4.3, 0.40), 28, 18),
        (156, (0.52, 3.55, 0.62), (MX + 0.2, 5.2, 0.2), 28, 16),
        (186, (0.40, 3.75, 1.95), (MX + 0.3, 5.6, 0.0), 24, 16)]
for f, loc, t_, lens, fs in path:
    key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
    cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
    cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
for idb in (cam, tgt, cam.data):
    set_interp(idb, "BEZIER")

mode = ARGS[0] if ARGS else "still"
if mode == "still":
    os.makedirs("/tmp/claude-0/x/s4", exist_ok=True)
    for f in [int(a) for a in ARGS[1:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"/tmp/claude-0/x/s4/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, "renders/scene_renders/scene_04"), int(ARGS[1]), int(ARGS[2]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
