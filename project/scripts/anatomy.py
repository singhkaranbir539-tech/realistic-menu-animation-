"""Glass-body anatomical rig shared by scene 1B and scene 5 (CT-derived meshes)."""
from bcommon import *


def glass_material(name="GlassSkin", edge=(0.25, 0.75, 1.0), edge_strength=1.2, gloss=0.15):
    m, n, l = mat(name); n.remove(n["Principled BSDF"])
    tr = n.new("ShaderNodeBsdfTransparent")
    gl = n.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.2
    lw = n.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.35
    gmul = n.new("ShaderNodeMath"); gmul.operation = "MULTIPLY"; l.new(lw.outputs["Fresnel"], gmul.inputs[0]); gmul.inputs[1].default_value = gloss
    mx = n.new("ShaderNodeMixShader"); l.new(gmul.outputs[0], mx.inputs[0]); l.new(tr.outputs[0], mx.inputs[1]); l.new(gl.outputs[0], mx.inputs[2])
    pw = n.new("ShaderNodeMath"); pw.operation = "POWER"; l.new(lw.outputs["Facing"], pw.inputs[0]); pw.inputs[1].default_value = 3.5
    st = n.new("ShaderNodeValue"); st.name = "EdgeGain"; st.outputs[0].default_value = edge_strength
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; l.new(pw.outputs[0], mul.inputs[0]); l.new(st.outputs[0], mul.inputs[1])
    em = n.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*edge, 1); l.new(mul.outputs[0], em.inputs["Strength"])
    ad = n.new("ShaderNodeAddShader"); l.new(mx.outputs[0], ad.inputs[0]); l.new(em.outputs[0], ad.inputs[1])
    l.new(ad.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def anat(name, color, rough=0.35, sss=0.6, coat=0.4, radius=(1, 0.3, 0.2), alpha_mix=0.0, bump_scale=90):
    m = principled(name, color, rough=rough, sss=sss, sss_radius=radius, sss_scale=0.004, coat=coat)
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = bump_scale; nz.inputs["Detail"].default_value = 6
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.25; bp.inputs["Distance"].default_value = 0.002
    l.new(nz.outputs["Fac"], bp.inputs["Height"]); l.new(bp.outputs[0], b.inputs["Normal"])
    if alpha_mix > 0:
        tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader"); mx.inputs[0].default_value = alpha_mix
        l.new(b.outputs[0], mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2]); l.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    return m


def cortex_material(gain=3.0):
    m, n, l = mat("CortexBody")
    b = n["Principled BSDF"]; b.subsurface_method = "BURLEY"
    b.inputs["Base Color"].default_value = (0.62, 0.44, 0.42, 1); b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1, 0.45, 0.35); b.inputs["Subsurface Scale"].default_value = 0.003
    b.inputs["Roughness"].default_value = 0.32; b.inputs["Coat Weight"].default_value = 0.5
    sp = n.new("ShaderNodeTexNoise"); sp.noise_dimensions = "4D"; sp.inputs["Scale"].default_value = 60; sp.inputs["Detail"].default_value = 2
    value_node_driver(sp.inputs["W"], "frame/45")
    spr = n.new("ShaderNodeMapRange"); spr.inputs["From Min"].default_value = 0.66; spr.inputs["From Max"].default_value = 0.74
    l.new(sp.outputs["Fac"], spr.inputs["Value"])
    g = n.new("ShaderNodeValue"); g.name = "SparkGain"; g.outputs[0].default_value = gain
    spm = n.new("ShaderNodeMath"); spm.operation = "MULTIPLY"; l.new(spr.outputs[0], spm.inputs[0]); l.new(g.outputs[0], spm.inputs[1])
    b.inputs["Emission Color"].default_value = (0.35, 0.6, 1.0, 1); l.new(spm.outputs[0], b.inputs["Emission Strength"])
    return m


def build(parent, skeleton_alpha=0.5, with_skin=True, decimate_skin=0.5):
    H = A("human_anatomy")
    objs = {}

    def part(name, path, dec=None):
        o = import_ply(path, name)
        if dec:
            decimate(o, dec)
        o.parent = parent
        objs[name] = o
        return o

    if with_skin:
        sk = part("Shell", f"{H}/skin.ply", decimate_skin)
        # the CT is defaced for privacy: smooth the face region so the glass shell reads as a neutral model
        import numpy as np
        co = np.array([v.co[:] for v in sk.data.vertices])
        wface = np.clip((-co[:, 1] - 0.03) / 0.04, 0, 1) * np.clip((co[:, 2] - 0.61) / 0.03, 0, 1)
        vg = sk.vertex_groups.new(name="face")
        for i in np.where(wface > 0)[0]:
            vg.add([int(i)], float(wface[i]), "REPLACE")
        smm = sk.modifiers.new("faceSmooth", "LAPLACIANSMOOTH"); smm.vertex_group = "face"
        smm.iterations = 40; smm.lambda_factor = 1.0; smm.use_volume_preserve = True
        assign(sk, glass_material())
        sk.visible_shadow = False
    sk2 = part("Skeleton", f"{H}/skeleton.ply", 0.35)
    assign(sk2, anat("Bone", (0.50, 0.45, 0.36), rough=0.55, sss=0.3, coat=0.05, alpha_mix=skeleton_alpha))
    spec = {
        "heart": ((0.40, 0.035, 0.03), dict(rough=0.28, coat=0.8)),
        "lungs": ((0.62, 0.30, 0.31), dict(rough=0.5, sss=0.8, alpha_mix=0.35, bump_scale=200)),
        "liver": ((0.30, 0.07, 0.05), dict(rough=0.3, coat=0.6)),
        "kidneys": ((0.35, 0.09, 0.07), {}),
        "gut": ((0.50, 0.30, 0.26), dict(sss=0.8)),
        "arteries": ((0.55, 0.03, 0.03), dict(coat=0.8)),
        "veins": ((0.10, 0.10, 0.34), dict(coat=0.8)),
        "airway": ((0.75, 0.62, 0.58), {}),
        "spinal_cord": ((0.85, 0.78, 0.70), {}),
    }
    for nm, (col, kw) in spec.items():
        o = part(nm, f"{H}/{nm}.ply", 0.5 if nm in ("gut", "lungs") else None)
        assign(o, anat(nm.capitalize(), col, **kw))
    cm = cortex_material()
    for h in ("left", "right"):
        o = part(f"cortex_{h}", A("brain", f"cortex_{h}_inbody.ply"))
        sb = o.modifiers.new("sub", "SUBSURF"); sb.levels = sb.render_levels = 1
        assign(o, cm)
    # fade everything out toward the CT field-of-view cut at the upper thighs
    for m_ in {mm for o in objs.values() for mm in o.data.materials}:
        n, l = m_.node_tree.nodes, m_.node_tree.links
        out = n["Material Output"]; src_ = out.inputs["Surface"].links[0].from_socket
        tcz = n.new("ShaderNodeTexCoord"); sep = n.new("ShaderNodeSeparateXYZ"); l.new(tcz.outputs["Object"], sep.inputs[0])
        mr = n.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.06; mr.inputs["From Max"].default_value = 0.24
        mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0; l.new(sep.outputs["Z"], mr.inputs["Value"])
        tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader")
        l.new(mr.outputs[0], mx.inputs[0]); l.new(src_, mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2]); l.new(mx.outputs[0], out.inputs["Surface"])
    # heartbeat (~62 bpm lub-dub) and breathing (~15 / min)
    bpy.ops.object.select_all(action="DESELECT")
    for nm in ("heart", "lungs"):
        o = objs[nm]; bpy.context.view_layer.objects.active = o; o.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS"); o.select_set(False)
    for i in range(3):
        fc = objs["heart"].driver_add("scale", i)
        fc.driver.expression = "1+0.04*max(0,sin(frame*0.2165))**12+0.022*max(0,sin(frame*0.2165-0.9))**12"
        fc2 = objs["lungs"].driver_add("scale", i)
        fc2.driver.expression = "1+0.03*sin(frame*0.0524)" if i == 1 else "1+0.018*sin(frame*0.0524)"
    return objs


def void_world(scene, top=(0.006, 0.012, 0.03)):
    w = scene.world.node_tree; wn = w.nodes
    grad = wn.new("ShaderNodeTexGradient"); grad.gradient_type = "SPHERICAL"
    wr = wn.new("ShaderNodeValToRGB"); wr.color_ramp.elements[0].color = (0, 0, 0, 1); wr.color_ramp.elements[1].color = (*top, 1)
    wtc = wn.new("ShaderNodeTexCoord"); w.links.new(wtc.outputs["Window"], grad.inputs[0])
    mp = wn.new("ShaderNodeMapping"); mp.inputs["Location"].default_value = (-0.5, -0.5, 0)
    w.links.new(wtc.outputs["Window"], mp.inputs[0]); w.links.new(mp.outputs[0], grad.inputs[0])
    w.links.new(grad.outputs[0], wr.inputs[0]); w.links.new(wr.outputs[0], wn["Background"].inputs[0])


def dust(n=200, box=((-1, 1), (-1, 1), (-1, 1)), radius=0.0012, color=(0.45, 0.65, 1.0), strength=1.2, seed=5):
    import numpy as np
    rng = np.random.default_rng(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius)
    d0 = bpy.context.object; d0.name = "dust"
    assign(d0, principled("Dust", color, emission=color, emission_strength=strength))
    for i in range(n):
        d = d0.copy(); bpy.context.collection.objects.link(d)
        d.location = Vector([rng.uniform(*box[k]) for k in range(3)])
        sc = rng.uniform(0.5, 2.0); d.scale = (sc, sc, sc)
    d0.hide_render = True
