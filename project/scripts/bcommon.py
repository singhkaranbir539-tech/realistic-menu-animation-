"""Shared Blender (bpy) helpers for all scenes."""
import bpy, math, os, sys, addon_utils
from mathutils import Vector, Euler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, "assets", *p)

FPS = 30


def reset(res=(1080, 1920), samples=48, engine="CYCLES"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = True
    s = bpy.context.scene
    s.render.engine = engine
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.02
    s.cycles.use_denoising = True
    s.cycles.denoiser = "OPENIMAGEDENOISE"
    try:
        s.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        s.cycles.denoising_prefilter = "ACCURATE"
    except Exception:
        pass
    s.cycles.max_bounces = 8
    s.cycles.transparent_max_bounces = 24
    s.cycles.transmission_bounces = 8
    s.cycles.volume_bounces = 1
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.cycles.blur_glossy = 1.0
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.fps = FPS
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_depth = "16"
    s.render.image_settings.color_mode = "RGB"
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.render.use_motion_blur = True
    s.render.motion_blur_shutter = 0.5
    s.render.film_transparent = False
    s.render.threads_mode = "AUTO"
    w = bpy.data.worlds.new("World"); s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.002, 0.004, 0.010, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    return s


def import_ply(path, name=None, smooth=True):
    bpy.ops.wm.ply_import(filepath=path)
    o = bpy.context.selected_objects[0]
    if name:
        o.name = name
    if smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    return o


def decimate(o, ratio):
    m = o.modifiers.new("dec", "DECIMATE"); m.ratio = ratio
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=m.name)


def mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def principled(name, color, rough=0.5, sss=0.0, sss_radius=(1, 0.4, 0.2), sss_scale=0.01, alpha=1.0,
               transmission=0.0, ior=1.4, emission=None, emission_strength=0.0, coat=0.0, spec=0.5):
    m, n, l = mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = sss_radius
    b.inputs["Subsurface Scale"].default_value = sss_scale
    b.inputs["Alpha"].default_value = alpha
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Specular IOR Level"].default_value = spec
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = emission_strength
    return m


def assign(o, m):
    o.data.materials.clear(); o.data.materials.append(m)


def camera(name="Cam", lens=50, loc=(0, -2, 1), target=None, sensor=36, fstop=None, focus_obj=None, focus_dist=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = sensor; cd.sensor_fit = "AUTO"
    c = bpy.data.objects.new(name, cd); bpy.context.collection.objects.link(c)
    c.location = loc
    if fstop:
        cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop
        if focus_obj: cd.dof.focus_object = focus_obj
        if focus_dist: cd.dof.focus_distance = focus_dist
    bpy.context.scene.camera = c
    if target is not None:
        look_at(c, target)
    return c


def look_at(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(e); e.location = loc
    return e


def track_to(o, target_obj):
    c = o.constraints.new("TRACK_TO"); c.target = target_obj
    c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    return c


def light(kind, name, loc, energy, color=(1, 1, 1), size=1.0, rot=None, target=None, spot=None):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if kind == "AREA":
        ld.size = size
    elif kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    if kind == "SPOT" and spot:
        ld.spot_size = spot
        ld.spot_blend = 0.6
    o = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(o); o.location = loc
    if rot:
        o.rotation_euler = rot
    if target is not None:
        look_at(o, target)
    return o


def key(obj, path, frame, value, index=-1, interp=None):
    if index >= 0:
        getattr(obj, path)[index] = value
    else:
        setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame, index=index)
    if interp:
        set_interp(obj, interp)


def set_interp(idblock, interp="BEZIER", easing=None):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    for fc in _fcurves(ad.action):
        for k in fc.keyframe_points:
            k.interpolation = interp
            if easing:
                k.easing = easing


def _fcurves(action):
    # Blender 4.4+ layered actions
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def value_node_driver(node_input, expr):
    """Drive a node socket default value with a python expression of 'frame'."""
    fc = node_input.driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = expr
    return fc


def output_setup(scene, outdir, start, end):
    os.makedirs(outdir, exist_ok=True)
    scene.frame_start = start; scene.frame_end = end
    scene.frame_step = int(os.environ.get("FRAME_STEP", "1"))
    if os.environ.get("FAST"):
        scene.cycles.samples = min(scene.cycles.samples, 16)
        scene.cycles.adaptive_threshold = max(scene.cycles.adaptive_threshold, 0.06)
    scene.render.filepath = os.path.join(outdir, "f_")
    scene.render.use_file_extension = True


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    return a
