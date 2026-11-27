"""Microscopic brain tissue - used for shot 2B (action potential -> synapse) and scene 3 (glymphatic flow).

Procedurally generated, scientifically grounded elements:
  * pyramidal-like neurons: soma + tapering branching dendrites + long axon with terminal boutons
  * action potentials: narrow travelling emissive fronts along axons (sparse, restrained)
  * an arteriole with a perivascular (Virchow-Robin) space bounded by astrocyte end-feet
  * cerebrospinal fluid particles flowing along the perivascular space (glymphatic influx/efflux)
  * metabolic waste aggregates (e.g. amyloid-beta) drifting out of the interstitium into that stream
Depth haze is computed per shader from camera distance (no volumetrics -> fast).
usage: python3 neural_tissue.py -- shot2b still 1 36 | -- shot3 still 1 90 186 | -- shot3 render 1 186
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts"))
from bcommon import *
import numpy as np

ARGS = args()
SHOT = ARGS[0]; MODE = ARGS[1]
s = reset(res=(720, 1280), samples=22)
s.cycles.adaptive_threshold = 0.05
s.cycles.use_fast_gi = True; s.cycles.ao_bounces_render = 1
s.cycles.max_bounces = 4; s.cycles.diffuse_bounces = 2; s.cycles.glossy_bounces = 2; s.cycles.transparent_max_bounces = 12
s.render.use_persistent_data = True
rng = np.random.default_rng(42)
FOG = (0.010, 0.018, 0.045)
s.world.node_tree.nodes["Background"].inputs[0].default_value = (*FOG, 1)

VESSEL_X, VESSEL_Z = 0.55, -0.25
R_VESSEL, R_SHEATH = 0.26, 0.40


# ------------------------------------------------------------------ helpers
def tube_mesh(name, polylines, segs=8):
    """polylines: list of (pts (n,3), radii (n,), svals (n,), extra attrs dict name->(n,))"""
    V, F, S, EX = [], [], [], {}
    off = 0
    for pts, rad, sv, ex in polylines:
        n = len(pts)
        if n < 2:
            continue
        t = np.gradient(pts, axis=0); t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-9
        a = np.cross(t[0], [0.31, 0.77, 0.55]); a /= np.linalg.norm(a)
        frames = []
        for i in range(n):
            a = a - t[i] * np.dot(a, t[i]); a /= np.linalg.norm(a) + 1e-9
            frames.append((a.copy(), np.cross(t[i], a)))
        ang = np.linspace(0, 2 * np.pi, segs, endpoint=False)
        for i in range(n):
            u, v = frames[i]
            ring = pts[i] + rad[i] * (np.outer(np.cos(ang), u) + np.outer(np.sin(ang), v))
            V.append(ring); S.append(np.full(segs, sv[i]))
            for k_, arr in ex.items():
                EX.setdefault(k_, []).append(np.full(segs, arr[i]))
        for i in range(n - 1):
            for j in range(segs):
                a0 = off + i * segs + j; a1 = off + i * segs + (j + 1) % segs
                F.append((a0, a1, a1 + segs, a0 + segs))
        tip = pts[-1] + t[-1] * rad[-1] * 0.5
        V.append(tip[None]); S.append(np.array([sv[-1]]))
        for k_, arr in ex.items():
            EX[k_].append(np.array([arr[-1]]))
        ti = off + n * segs
        for j in range(segs):
            F.append((off + (n - 1) * segs + j, off + (n - 1) * segs + (j + 1) % segs, ti))
        off += n * segs + 1
    V = np.concatenate(V); S = np.concatenate(S)
    me = bpy.data.meshes.new(name); me.from_pydata(V.tolist(), [], F); me.update()
    at = me.attributes.new("s", "FLOAT", "POINT"); at.data.foreach_set("value", S.astype(np.float32))
    for k_, lst in EX.items():
        at = me.attributes.new(k_, "FLOAT", "POINT"); at.data.foreach_set("value", np.concatenate(lst).astype(np.float32))
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o


def grow(p, d, r, s0, depth, length, out, rid, step=0.02, branch_p=0.06, max_depth=3, wander=0.28):
    pts, rad, sv = [p.copy()], [r], [s0]
    L = 0.0; cur = p.copy(); dd = d / np.linalg.norm(d)
    while L < length:
        dd = dd + rng.normal(0, wander, 3) * step * 6; dd /= np.linalg.norm(dd)
        cur = cur + dd * step; L += step
        rr = max(0.0035, r * (1 - 0.75 * L / length))
        pts.append(cur.copy()); rad.append(rr); sv.append(s0 + L)
        if depth < max_depth and rng.random() < branch_p and L > 0.06:
            nd = dd + rng.normal(0, 0.9, 3); nd /= np.linalg.norm(nd)
            grow(cur, nd, rr * 0.8, s0 + L, depth + 1, length * rng.uniform(0.45, 0.7), out, rid, step, branch_p, max_depth, wander)
    out.append((np.array(pts), np.array(rad), np.array(sv), {"rid": np.full(len(pts), rid), "hero": np.zeros(len(pts))}))


def fogwrap(m, density=0.55):
    n, l = m.node_tree.nodes, m.node_tree.links
    out = n["Material Output"]; src = out.inputs["Surface"].links[0].from_socket
    cd = n.new("ShaderNodeCameraData")
    ex = n.new("ShaderNodeMath"); ex.operation = "MULTIPLY"; l.new(cd.outputs["View Distance"], ex.inputs[0]); ex.inputs[1].default_value = -density
    e2 = n.new("ShaderNodeMath"); e2.operation = "EXPONENT"; l.new(ex.outputs[0], e2.inputs[0])
    fac = n.new("ShaderNodeMath"); fac.operation = "SUBTRACT"; fac.inputs[0].default_value = 1.0; l.new(e2.outputs[0], fac.inputs[1])
    em = n.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*FOG, 1); em.inputs["Strength"].default_value = 1.0
    mx = n.new("ShaderNodeMixShader"); l.new(fac.outputs[0], mx.inputs[0]); l.new(src, mx.inputs[1]); l.new(em.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])
    return m


def near_fade(m, d0=0.05, d1=0.16):
    n, l = m.node_tree.nodes, m.node_tree.links
    out = n["Material Output"]; src = out.inputs["Surface"].links[0].from_socket
    cd = n.new("ShaderNodeCameraData")
    mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = d0; mr.inputs["From Max"].default_value = d1
    mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0
    l.new(cd.outputs["View Distance"], mr.inputs["Value"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader"); l.new(mr.outputs[0], mx.inputs[0]); l.new(src, mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs["Surface"])


# ------------------------------------------------------------------ neurons
somas = []
polylines = []
NEUR = []
hero_soma = np.array([-0.35, 0.25, 0.10])
for i in range(16):
    if i == 0:
        c = hero_soma
    else:
        c = np.array([rng.uniform(-2.2, 1.6), rng.uniform(-3.5, 6.0), rng.uniform(-1.0, 1.4)])
        if abs(c[0] - VESSEL_X) < 0.55 and abs(c[2] - VESSEL_Z) < 0.55:
            c[2] += 0.9
    NEUR.append(c)
    rs = rng.uniform(0.055, 0.08)
    somas.append((c, rs))
    up = np.array([0, 0, 1.0]) + rng.normal(0, 0.3, 3)
    grow(c + up / np.linalg.norm(up) * rs * 0.8, up, rs * 0.42, 0.0, 0, rng.uniform(0.9, 1.4), polylines, i)   # apical dendrite
    for k in range(rng.integers(4, 7)):
        d = rng.normal(0, 1, 3); d[2] -= 0.4
        grow(c + d / np.linalg.norm(d) * rs * 0.8, d, rs * 0.3, 0.0, 1, rng.uniform(0.35, 0.7), polylines, i)
    # axon: long, thin, few branches; ends in boutons
    ad = rng.normal(0, 1, 3); ad[2] = -abs(ad[2]) - 0.6
    if i == 0:
        ad = np.array([0.55, -0.9, -0.35])
    pre = len(polylines)
    grow(c - np.array([0, 0, rs * 0.8]), ad, 0.014, 0.0, 2, rng.uniform(1.6, 2.4), polylines, i, branch_p=0.02, max_depth=3, wander=0.12)
    for k in range(pre, len(polylines)):
        pts, rad, sv, ex = polylines[k]
        rad[:] = np.maximum(rad, 0.008)
        ex["axon"] = np.ones(len(pts))
        if i == 0:
            ex["hero"] = np.ones(len(pts))
for pl in polylines:
    pl[3].setdefault("axon", np.zeros(len(pl[0])))
neurites = tube_mesh("Neurites", polylines)

# somata (displaced spheres, slightly pyramidal)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=1.0)
soma0 = bpy.context.object; soma0.name = "soma0"
for v in soma0.data.vertices:
    c = v.co
    c.z *= 1.15 + 0.25 * max(0, c.z)
for p in soma0.data.polygons:
    p.use_smooth = True
sd = soma0.modifiers.new("d", "DISPLACE"); stx = bpy.data.textures.new("st", "CLOUDS"); stx.noise_scale = 0.4; sd.texture = stx; sd.strength = 0.12
soma_objs = []
for i, (c, rs) in enumerate(somas):
    o = soma0.copy(); o.data = soma0.data; bpy.context.collection.objects.link(o)
    o.location = Vector(c); o.scale = (rs, rs, rs); o.rotation_euler = Euler(rng.uniform(0, 0.4, 3))
    soma_objs.append(o)
soma0.hide_render = True; soma0.hide_viewport = True

# boutons at axon tips
bout = []
for pts, rad, sv, ex in polylines:
    if ex["axon"][0] > 0:
        bout.append(pts[-1])
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.022, segments=16, ring_count=10)
b0 = bpy.context.object; b0.name = "bouton"
for p in b0.data.polygons:
    p.use_smooth = True
bobjs = []
for pnt in bout:
    o = b0.copy(); bpy.context.collection.objects.link(o); o.location = Vector(pnt); bobjs.append(o)
b0.hide_render = True

# ------------------------------------------------------------------ materials
m, n, l = mat("Membrane")
b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
b.inputs["Base Color"].default_value = (0.36, 0.40, 0.62, 1)
b.inputs["Subsurface Weight"].default_value = 1.0; b.inputs["Subsurface Radius"].default_value = (0.6, 0.7, 1.0)
b.inputs["Subsurface Scale"].default_value = 0.03; b.inputs["Roughness"].default_value = 0.35; b.inputs["Coat Weight"].default_value = 0.6
tc = n.new("ShaderNodeTexCoord")
bn = n.new("ShaderNodeTexNoise"); bn.inputs["Scale"].default_value = 60; bn.inputs["Detail"].default_value = 5
l.new(tc.outputs["Object"], bn.inputs["Vector"])
bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; bp.inputs["Distance"].default_value = 0.004
l.new(bn.outputs["Fac"], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
# action potentials: front position = frame*speed + per-neuron phase ; travels outward along s (from soma)
sA = n.new("ShaderNodeAttribute"); sA.attribute_name = "s"
rA = n.new("ShaderNodeAttribute"); rA.attribute_name = "rid"
hA = n.new("ShaderNodeAttribute"); hA.attribute_name = "hero"
axA = n.new("ShaderNodeAttribute"); axA.attribute_name = "axon"
fr = n.new("ShaderNodeValue"); fr.name = "frame"; value_node_driver(fr.outputs[0], "frame")
ph = n.new("ShaderNodeMath"); ph.operation = "MULTIPLY"; l.new(rA.outputs["Fac"], ph.inputs[0]); ph.inputs[1].default_value = 1.37
sp = n.new("ShaderNodeMath"); sp.operation = "MULTIPLY_ADD"; l.new(fr.outputs[0], sp.inputs[0]); sp.inputs[1].default_value = 0.045; l.new(ph.outputs[0], sp.inputs[2])
dx = n.new("ShaderNodeMath"); dx.operation = "SUBTRACT"; l.new(sp.outputs[0], dx.inputs[0]); l.new(sA.outputs["Fac"], dx.inputs[1])
md = n.new("ShaderNodeMath"); md.operation = "FLOORED_MODULO"; l.new(dx.outputs[0], md.inputs[0]); md.inputs[1].default_value = 3.2
win = n.new("ShaderNodeMapRange"); win.inputs["From Min"].default_value = 0.0; win.inputs["From Max"].default_value = 0.12
win.inputs["To Min"].default_value = 1.0; win.inputs["To Max"].default_value = 0.0
l.new(md.outputs[0], win.inputs["Value"])
nh = n.new("ShaderNodeMath"); nh.operation = "SUBTRACT"; nh.inputs[0].default_value = 1.0; l.new(hA.outputs["Fac"], nh.inputs[1])
gen = n.new("ShaderNodeMath"); gen.operation = "MULTIPLY"; l.new(win.outputs[0], gen.inputs[0]); l.new(nh.outputs[0], gen.inputs[1])
# hero axon: keyframed front
hf = n.new("ShaderNodeValue"); hf.name = "HeroFront"; hf.outputs[0].default_value = -1
hd = n.new("ShaderNodeMath"); hd.operation = "SUBTRACT"; l.new(hf.outputs[0], hd.inputs[0]); l.new(sA.outputs["Fac"], hd.inputs[1])
hw = n.new("ShaderNodeMapRange"); hw.inputs["From Min"].default_value = 0.0; hw.inputs["From Max"].default_value = 0.22
hw.inputs["To Min"].default_value = 1.0; hw.inputs["To Max"].default_value = 0.0; l.new(hd.outputs[0], hw.inputs["Value"])
hw2 = n.new("ShaderNodeMapRange"); hw2.inputs["From Min"].default_value = -0.02; hw2.inputs["From Max"].default_value = 0.0
l.new(hd.outputs[0], hw2.inputs["Value"])
hwin = n.new("ShaderNodeMath"); hwin.operation = "MULTIPLY"; l.new(hw.outputs[0], hwin.inputs[0]); l.new(hw2.outputs[0], hwin.inputs[1])
hsel = n.new("ShaderNodeMath"); hsel.operation = "MULTIPLY"; l.new(hwin.outputs[0], hsel.inputs[0]); l.new(hA.outputs["Fac"], hsel.inputs[1])
tot = n.new("ShaderNodeMath"); tot.operation = "ADD"; l.new(gen.outputs[0], tot.inputs[0]); l.new(hsel.outputs[0], tot.inputs[1])
gain = n.new("ShaderNodeValue"); gain.name = "APGain"; gain.outputs[0].default_value = 4.0
st_ = n.new("ShaderNodeMath"); st_.operation = "MULTIPLY"; l.new(tot.outputs[0], st_.inputs[0]); l.new(gain.outputs[0], st_.inputs[1])
b.inputs["Emission Color"].default_value = (0.45, 0.8, 1.0, 1); l.new(st_.outputs[0], b.inputs["Emission Strength"])
fogwrap(m)
if SHOT == "shot3":
    near_fade(m)
assign(neurites, m)

ms = principled("Soma", (0.52, 0.50, 0.75), rough=0.4, sss=1.0, sss_radius=(0.6, 0.7, 1.0), sss_scale=0.04, coat=0.5)
ms.node_tree.nodes["Principled BSDF"].subsurface_method = "BURLEY"
nb = ms.node_tree.nodes.new("ShaderNodeTexNoise"); nb.inputs["Scale"].default_value = 25
bb = ms.node_tree.nodes.new("ShaderNodeBump"); bb.inputs["Strength"].default_value = 0.3
ms.node_tree.links.new(nb.outputs["Fac"], bb.inputs["Height"]); ms.node_tree.links.new(bb.outputs[0], ms.node_tree.nodes["Principled BSDF"].inputs["Normal"])
fogwrap(ms)
if SHOT == "shot3":
    near_fade(ms, 0.08, 0.25)
for o in soma_objs:
    assign(o, ms)
mb = principled("Bouton", (0.6, 0.5, 0.85), rough=0.3, sss=1.0, sss_scale=0.03, emission=(0.5, 0.75, 1.0), emission_strength=0.35)
fogwrap(mb)
for o in bobjs:
    assign(o, mb)

# ------------------------------------------------------------------ arteriole + perivascular space + astrocytes
def cyl(name, r, y0=-5, y1=9, segs=96, ring=280, wob=0.0):
    pts = np.stack([np.full(ring, VESSEL_X), np.linspace(y0, y1, ring), np.full(ring, VESSEL_Z)], 1)
    pts[:, 0] += 0.08 * np.sin(pts[:, 1] * 0.5); pts[:, 2] += 0.06 * np.sin(pts[:, 1] * 0.37 + 1)
    o = tube_mesh(name, [(pts, np.full(ring, r), pts[:, 1], {})], segs=segs)
    return o, pts


vessel, AXIS = cyl("Arteriole", R_VESSEL)
sheath, _ = cyl("PerivascularSheath", R_SHEATH)
mv, nv, lv = mat("VesselWall")
bv = nv["Principled BSDF"]; bv.subsurface_method = "BURLEY"
tcv = nv.new("ShaderNodeTexCoord")
vo = nv.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 9; lv.new(tcv.outputs["Object"], vo.inputs["Vector"])
vr = nv.new("ShaderNodeValToRGB"); vr.color_ramp.elements[0].color = (0.45, 0.06, 0.07, 1); vr.color_ramp.elements[1].color = (0.65, 0.18, 0.18, 1)
lv.new(vo.outputs["Distance"], vr.inputs[0]); lv.new(vr.outputs[0], bv.inputs["Base Color"])
bv.inputs["Subsurface Weight"].default_value = 1.0; bv.inputs["Subsurface Radius"].default_value = (1.0, 0.25, 0.2); bv.inputs["Subsurface Scale"].default_value = 0.05
bv.inputs["Roughness"].default_value = 0.3; bv.inputs["Coat Weight"].default_value = 0.8
vb = nv.new("ShaderNodeBump"); vb.inputs["Strength"].default_value = 0.4; lv.new(vo.outputs["Distance"], vb.inputs["Height"]); lv.new(vb.outputs[0], bv.inputs["Normal"])
trv = nv.new("ShaderNodeBsdfTransparent"); mxv = nv.new("ShaderNodeMixShader"); mxv.inputs[0].default_value = 0.12
lv.new(bv.outputs[0], mxv.inputs[1]); lv.new(trv.outputs[0], mxv.inputs[2]); lv.new(mxv.outputs[0], nv["Material Output"].inputs["Surface"])
fogwrap(mv); assign(vessel, mv)
# sheath: patchwork of astrocyte end-feet, translucent
mh, nh_, lh = mat("EndFeet")
bh = nh_["Principled BSDF"]
tch = nh_.new("ShaderNodeTexCoord")
vh = nh_.new("ShaderNodeTexVoronoi"); vh.feature = "DISTANCE_TO_EDGE"; vh.inputs["Scale"].default_value = 5; lh.new(tch.outputs["Object"], vh.inputs["Vector"])
edge = nh_.new("ShaderNodeMapRange"); edge.inputs["From Min"].default_value = 0.0; edge.inputs["From Max"].default_value = 0.06
edge.inputs["To Min"].default_value = 1.0; edge.inputs["To Max"].default_value = 0.0; lh.new(vh.outputs["Distance"], edge.inputs["Value"])
bh.inputs["Base Color"].default_value = (0.45, 0.6, 0.85, 1); bh.inputs["Roughness"].default_value = 0.25
bh.inputs["Emission Color"].default_value = (0.3, 0.6, 1.0, 1)
em_s = nh_.new("ShaderNodeMath"); em_s.operation = "MULTIPLY"; lh.new(edge.outputs[0], em_s.inputs[0]); em_s.inputs[1].default_value = 0.5
lh.new(em_s.outputs[0], bh.inputs["Emission Strength"])
hb_ = nh_.new("ShaderNodeBump"); hb_.inputs["Strength"].default_value = 0.5; lh.new(vh.outputs["Distance"], hb_.inputs["Height"]); lh.new(hb_.outputs[0], bh.inputs["Normal"])
trh = nh_.new("ShaderNodeBsdfTransparent"); mxh = nh_.new("ShaderNodeMixShader")
alpha = nh_.new("ShaderNodeMath"); alpha.operation = "MULTIPLY_ADD"; lh.new(edge.outputs[0], alpha.inputs[0]); alpha.inputs[1].default_value = -0.45; alpha.inputs[2].default_value = 0.72
lh.new(alpha.outputs[0], mxh.inputs[0]); lh.new(bh.outputs[0], mxh.inputs[1]); lh.new(trh.outputs[0], mxh.inputs[2])
lh.new(mxh.outputs[0], nh_["Material Output"].inputs["Surface"])
fogwrap(mh); assign(sheath, mh)
sheath.visible_shadow = False

# astrocytes hugging the vessel, processes reaching out into the neuropil
apl = []
for i in range(10):
    yy = rng.uniform(-3.0, 7.0); ang = rng.uniform(0, 2 * np.pi)
    k = np.argmin(np.abs(AXIS[:, 1] - yy)); ax = AXIS[k]
    c = ax + np.array([np.cos(ang), 0, np.sin(ang)]) * (R_SHEATH + 0.12)
    for j in range(18):
        d = rng.normal(0, 1, 3)
        if j < 4:
            d = (ax - c) + rng.normal(0, 0.2, 3)
        grow(c, d, 0.012, 0.0, 2, rng.uniform(0.15, 0.4), apl, 100 + i, step=0.015, branch_p=0.08, wander=0.5)
astro = tube_mesh("Astrocytes", apl, segs=6)
ma = principled("Astro", (0.42, 0.62, 0.70), rough=0.35, sss=1.0, sss_radius=(0.5, 0.8, 1.0), sss_scale=0.03, coat=0.4)
fogwrap(ma)
if SHOT == "shot3":
    near_fade(ma)
assign(astro, ma)

# ------------------------------------------------------------------ CSF + waste particles (positions updated per frame)
NC, NW = 520, 140
csf_r = rng.uniform(R_VESSEL + 0.03, R_SHEATH - 0.03, NC); csf_a = rng.uniform(0, 2 * np.pi, NC)
csf_y = rng.uniform(-5, 9, NC); csf_v = rng.uniform(0.008, 0.016, NC)
w_start = np.stack([rng.uniform(-0.6, 0.6, NW) + VESSEL_X, rng.uniform(-3, 8, NW), rng.uniform(-0.6, 0.6, NW) + VESSEL_Z], 1)
w_start[:, 0] += np.sign(w_start[:, 0] - VESSEL_X) * 0.45; w_start[:, 2] += np.sign(w_start[:, 2] - VESSEL_Z) * 0.45
w_size = rng.uniform(0.6, 1.4, NW)


def axis_at(y):
    return np.stack([VESSEL_X + 0.08 * np.sin(y * 0.5), y, VESSEL_Z + 0.06 * np.sin(y * 0.37 + 1)], -1)


def csf_pos(f):
    y = (csf_y + csf_v * f + 5) % 14 - 5
    a = csf_a + 0.004 * f
    c = axis_at(y)
    return c + np.stack([np.cos(a) * csf_r, np.zeros(NC), np.sin(a) * csf_r], 1)


def waste_pos(f):
    # drift radially toward the perivascular stream, then get carried along it
    out = np.empty((NW, 3))
    for i in range(NW):
        p = w_start[i].copy()
        c = axis_at(np.array([p[1]]))[0]
        rv = p - c; rv[1] = 0; r0 = np.linalg.norm(rv); u = rv / r0
        t_arrive = (r0 - (R_VESSEL + R_SHEATH) / 2) / 0.006
        if f < t_arrive:
            r = r0 - 0.006 * f; y = p[1] + 0.001 * f
        else:
            r = (R_VESSEL + R_SHEATH) / 2; y = p[1] + 0.001 * t_arrive + 0.011 * (f - t_arrive)
        cc = axis_at(np.array([y]))[0]
        out[i] = cc + u * r + np.array([0, 0, 0.01 * np.sin(f * 0.1 + i)])
    return out


def particle_mesh(name, nparts, radius, subdiv, irregular=0.0):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius)
    proto = bpy.context.object
    pv = np.array([v.co[:] for v in proto.data.vertices]); pf = [tuple(p.vertices) for p in proto.data.polygons]
    bpy.data.objects.remove(proto)
    V, F = [], []
    for i in range(nparts):
        vv = pv * (1 + irregular * rng.normal(0, 1, pv.shape)) if irregular else pv
        V.append(vv); F += [tuple(x + i * len(pv) for x in f) for f in pf]
    me = bpy.data.meshes.new(name); me.from_pydata(np.concatenate(V).tolist(), [], F); me.update()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = True
    return o, np.concatenate(V), len(pv)


csf_o, csf_base, csf_k = particle_mesh("CSF", NC, 0.0065, 1)
waste_o, waste_base, waste_k = particle_mesh("Waste", NW, 0.012, 2, irregular=0.18)
waste_base = waste_base * np.repeat(w_size, waste_k)[:, None]
mc = principled("CSF", (0.3, 0.6, 0.8), rough=0.2, emission=(0.35, 0.8, 1.0), emission_strength=1.6)
fogwrap(mc); assign(csf_o, mc)
mw_ = principled("Waste", (0.55, 0.32, 0.12), rough=0.6, sss=0.5, emission=(0.9, 0.45, 0.15), emission_strength=0.35)
fogwrap(mw_); assign(waste_o, mw_)
csf_o.visible_shadow = False


def update_particles(scene, depsgraph=None):
    f = scene.frame_current + scene.frame_subframe
    pc = np.repeat(csf_pos(f), csf_k, axis=0) + csf_base
    csf_o.data.vertices.foreach_set("co", pc.astype(np.float32).ravel()); csf_o.data.update()
    pw = np.repeat(waste_pos(f), waste_k, axis=0) + waste_base
    waste_o.data.vertices.foreach_set("co", pw.astype(np.float32).ravel()); waste_o.data.update()


bpy.app.handlers.frame_change_pre.clear()
bpy.app.handlers.frame_change_pre.append(update_particles)

# ------------------------------------------------------------------ lights
for yy in np.linspace(-3, 8, 6):
    c_ = axis_at(np.array([yy]))[0]
    light("POINT", f"Lumen{yy:.0f}", tuple(c_), 6.0, color=(1.0, 0.18, 0.12), size=0.1)
light("AREA", "Top", (0.0, 1.5, 3.0), 150, color=(0.55, 0.7, 1.0), size=4.0, target=(0, 1.5, 0))
light("AREA", "RimV", (2.5, 4.0, 1.0), 110, color=(0.6, 0.4, 1.0), size=3.0, target=(0, 1.0, 0))
light("AREA", "Under", (-1.5, -1.0, -2.2), 60, color=(0.25, 0.7, 1.0), size=3.0, target=(0, 1.0, 0))

# ------------------------------------------------------------------ cameras
tgt = empty("CamTarget", (0, 0, 0))
cam = camera(lens=35, loc=(0, -2, 0.3), fstop=2.0, focus_obj=tgt); track_to(cam, tgt)
cam.data.clip_start = 0.002
# locate the hero axon's polyline (longest hero branch) for 2B
hero_lines = [pl for pl in polylines if pl[3]["hero"][0] > 0]
hl_ = max(hero_lines, key=lambda p: len(p[0]))
hp_, hs_ = hl_[0], hl_[2]
term = hp_[-1]
if SHOT == "shot2b":
    s.frame_start, s.frame_end = 1, 40
    # camera close to the axon terminal, looking back along the axon toward the soma; pulse arrives at f32
    mid = hp_[len(hp_) // 2]
    dirv = (hp_[-1] - hp_[-12]); dirv /= np.linalg.norm(dirv)
    side = np.cross(dirv, [0, 0, 1]); side /= np.linalg.norm(side)
    c0 = term + dirv * 0.28 + side * 0.10 + np.array([0, 0, 0.06])
    c1 = term + dirv * 0.11 + side * 0.04 + np.array([0, 0, 0.025])
    for f, loc, t_, fs in [(1, c0, mid, 90.0), (40, c1, term, 128.0)]:
        key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
        cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
    cam.data.lens = 50
    smax = float(hs_[-1])
    for f, v in [(1, smax - 1.1), (32, smax + 0.02), (40, smax + 0.3)]:
        hf.outputs[0].default_value = v; hf.outputs[0].keyframe_insert("default_value", frame=f)
    set_interp(m.node_tree, "LINEAR")
    gain.outputs[0].default_value = 6.0
else:
    s.frame_start, s.frame_end = 1, 186
    # forward tracking through the neuropil, converging onto the vessel, then along the perivascular stream,
    # finally pushing through the vessel wall (-> scene 4 inside the bloodstream)
    path = [(1, (-0.6, -2.6, 0.55), (0.0, -1.0, 0.2), 30, 2.8),
            (60, (0.05, -1.2, 0.30), (0.45, 0.4, -0.1), 30, 2.4),
            (110, (0.38, 0.4, -0.02), axis_at(np.array([2.2]))[0] + [0, 0, 0.05], 28, 2.0),
            (150, axis_at(np.array([1.6]))[0] + [-0.31, 0, 0.10], axis_at(np.array([3.4]))[0] + [-0.30, 0, 0.06], 26, 3.5),
            (176, axis_at(np.array([2.5]))[0] + [-0.30, 0, 0.06], axis_at(np.array([3.8]))[0] + [-0.12, 0, 0.0], 24, 3.5),
            (186, axis_at(np.array([2.9]))[0] + [-0.20, 0, 0.03], axis_at(np.array([4.2]))[0], 24, 3.5)]
    for f, loc, t_, lens, fs in path:
        key(cam, "location", f, Vector(loc)); key(tgt, "location", f, Vector(t_))
        cam.data.lens = lens; cam.data.keyframe_insert("lens", frame=f)
        cam.data.dof.aperture_fstop = fs; cam.data.dof.keyframe_insert("aperture_fstop", frame=f)
for idb in (cam, tgt, cam.data):
    set_interp(idb, "BEZIER")

if MODE == "still":
    od = f"/tmp/claude-0/x/{SHOT}"; os.makedirs(od, exist_ok=True)
    for f in [int(a) for a in ARGS[2:] if a.isdigit()]:
        s.frame_set(f); s.render.filepath = f"{od}/f{f:03d}.png"
        import time; t0 = time.time(); bpy.ops.render.render(write_still=True); print("frame", f, "time", round(time.time() - t0, 1), flush=True)
else:
    output_setup(s, os.path.join(ROOT, f"renders/scene_renders/{SHOT}"), int(ARGS[2]), int(ARGS[3]))
    s.render.use_overwrite = False; s.render.use_placeholder = True
    bpy.ops.render.render(animation=True)
