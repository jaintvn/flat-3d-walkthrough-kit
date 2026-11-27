"""Balcony / window view renders: the untouched interior (flat_typeG.blend) + the linked exterior (environment.blend).

Blender -b blender/flat_typeG.blend -P env_render.py -- <outdir> <view,view|all> [samples] [width]

The interior file is NOT saved; the only change in memory is hiding the old placeholder context
(CTX_Ground / CTX_Buildings / CTX_Trees / CTX_Facade), which the environment replaces.
Distance haze: Cycles mist pass composited with an aerial-perspective colour (Kerala morning haze, ~10 km visibility).
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
VIEWS = argv[1].split(",") if len(argv) > 1 else ["all"]
SAMPLES = int(argv[2]) if len(argv) > 2 else 128
WIDTH = int(argv[3]) if len(argv) > 3 else 1600
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "..", "environment.blend")
sc = bpy.context.scene

# ---------------------------------------------------------------- replace placeholder context
for n in ("CTX_Ground", "CTX_Buildings", "CTX_Trees", "CTX_Facade"):
    ob = bpy.data.objects.get(n)
    if ob:
        ob.hide_render = True
        ob.hide_viewport = True
with bpy.data.libraries.load(ENV, link=True) as (src, dst):
    dst.collections = [c for c in src.collections if c == "06_Environment"]
env = dst.collections[0]
sc.collection.children.link(env)

# ---------------------------------------------------------------- engine
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.sample_clamp_indirect = 8.0
sc.cycles.max_bounces = 6
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
sc.view_settings.exposure = 0.35
sc.render.resolution_x = WIDTH
sc.render.resolution_y = int(WIDTH * 9 / 16)
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.render.film_transparent = False

# ---------------------------------------------------------------- haze (mist pass composite)
vl = sc.view_layers[0]
vl.use_pass_mist = True
w = sc.world
w.mist_settings.start = 60.0
w.mist_settings.depth = 9000.0
w.mist_settings.falloff = "QUADRATIC"
HAZE = (0.56, 0.62, 0.70, 1.0)
HAZE_MAX = 0.85


def setup_comp():
    """aerial perspective on geometry only: f = 0.85 * (1 - exp(-d / 6 km)); the sky comes from the Environment
    pass (film is transparent), so the haze never washes out the sky itself"""
    sc.render.film_transparent = True
    vl.use_pass_environment = True
    w.mist_settings.start = 0.0
    w.mist_settings.depth = 30000.0
    w.mist_settings.falloff = "LINEAR"
    try:   # Blender 5.x: compositor is a node group assigned to the scene
        ng = bpy.data.node_groups.new("ENV_Comp", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        N, L = ng.nodes, ng.links
        rl = N.new("CompositorNodeRLayers")
        out = N.new("NodeGroupOutput")
        sc.compositing_node_group = ng
    except Exception:
        sc.use_nodes = True
        ng = sc.node_tree
        N, L = ng.nodes, ng.links
        for n in list(N):
            N.remove(n)
        rl = N.new("CompositorNodeRLayers")
        out = N.new("CompositorNodeComposite")
    def math_node(op, a=None, b=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        if a is not None:
            n.inputs[0].default_value = a
        if b is not None:
            n.inputs[1].default_value = b
        return n
    m1 = math_node("MULTIPLY", None, -5.0)          # -d/6km  (mist = d/30km)
    ex = math_node("EXPONENT")
    m2 = math_node("SUBTRACT", 1.0)
    m3 = math_node("MULTIPLY", None, HAZE_MAX)
    L.new(rl.outputs["Mist"], m1.inputs[0])
    L.new(m1.outputs[0], ex.inputs[0])
    L.new(ex.outputs[0], m2.inputs[1])
    L.new(m2.outputs[0], m3.inputs[0])
    hz = N.new("ShaderNodeMix")
    hz.data_type = "RGBA"
    hz.inputs["B"].default_value = HAZE
    L.new(m3.outputs[0], hz.inputs["Factor"])
    L.new(rl.outputs["Image"], hz.inputs["A"])
    fin = N.new("ShaderNodeMix")
    fin.data_type = "RGBA"
    L.new(rl.outputs["Alpha"], fin.inputs["Factor"])
    L.new(rl.outputs["Environment"], fin.inputs["A"])
    L.new(hz.outputs["Result"], fin.inputs["B"])
    L.new(fin.outputs["Result"], out.inputs[0])


setup_comp()

# ---------------------------------------------------------------- cameras (flat frame, metres; +Y = 130 deg)
def bearing_dir(b):
    r130, r220 = math.radians(130), math.radians(220)
    e, n = math.sin(math.radians(b)), math.cos(math.radians(b))
    return Vector((e * math.sin(r220) + n * math.cos(r220), e * math.sin(r130) + n * math.cos(r130), 0)).normalized()


VIEWS_DEF = {
    # name: (eye, bearing, pitch deg, lens mm)
    "bal2_from_dining": ((10.55, 2.6, 1.60), 130, -3, 24),
    "bal2_rail": ((10.55, 5.25, 1.62), 130, -10, 24),
    "bal2_rail_left": ((10.55, 5.25, 1.62), 108, -4, 30),
    "bal2_rail_right": ((10.55, 5.25, 1.62), 160, -12, 24),
    "bal2_down": ((10.55, 5.30, 1.62), 130, -35, 24),
    "bal1_rail": ((0.60, 5.25, 1.62), 130, -8, 24),
    "bed1_window": ((2.6, 1.95, 1.50), 40, -5, 24),
}


def make_cam(name, eye, bearing, pitch, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.05
    cd.clip_end = 40000
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    ob.location = eye
    d = bearing_dir(bearing)
    yaw = math.atan2(d.y, d.x) - math.pi / 2
    ob.rotation_euler = (math.radians(90 + pitch), 0, yaw)
    return ob


todo = list(VIEWS_DEF) if VIEWS == ["all"] else VIEWS
for v in todo:
    cam = make_cam("CAM_" + v, *VIEWS_DEF[v])
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, v + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", v)
