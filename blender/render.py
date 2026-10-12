"""Lighting, grass and cameras for the Yellow House model; renders preview stills with Cycles.

python3 render.py <out_dir> [--views a,b] [--res 1280x720] [--samples 64] [--nograss] [--save path.blend]
"""
import argparse
import math
import os
import sys

import bpy  # noqa: I001
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--views", default="street,aerial,drive,back,porch")
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--nograss", action="store_true")
ap.add_argument("--save", default="")
ap.add_argument("--sun", default="225,32")  # azimuth (deg from north, clockwise), elevation
args = ap.parse_args(sys.argv[1:])

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "yellow_house_raw.blend"))
scene = bpy.context.scene
C_RENDER = bpy.data.collections["Render Only"]


def T(x, y, z):
    return Vector((x, -z, y))


# ------------------------------------------------------------ world + sun
# House front faces south: Blender -Y = south, +X = east (app +x is to the right seen from the street).
az, el = (float(v) for v in args.sun.split(","))
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_disc = False
sky.sun_elevation = math.radians(el)
sky.sun_rotation = math.radians(180 - az)  # Blender sky: rotation measured from -Y toward +X
sky.altitude = 120
sky.air_density = 1.0
try:
    sky.aerosol_density = 1.6
except AttributeError:
    sky.dust_density = 1.6
nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.18

sun_d = bpy.data.lights.new("Sun", "SUN")
sun_d.energy = 3.6
sun_d.angle = math.radians(0.8)
sun_d.color = (1.0, 0.93, 0.84)
sun = bpy.data.objects.new("Sun", sun_d)
C_RENDER.objects.link(sun)
to_sun = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)), math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()

# ------------------------------------------------------------ grass (hair particles, render only)
if not args.nograss:
    def pip(x, z, poly):
        ins = False
        n = len(poly)
        for i in range(n):
            x1, z1 = poly[i]
            x2, z2 = poly[(i + 1) % n]
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
                ins = not ins
        return ins

    BLOCK = [
        [(9.4, -15.2), (16.6, -15.2), (16.6, -9.3), (14.7, -8.1), (14.1, -7.2), (14.1, 22.8), (15.1, 24.5), (9.2, 24.5), (10.2, 22.8), (10.2, -7.6), (9.4, -8.7)],
        [(7.9, -10.0), (9.8, -10.0), (9.8, -14.0), (7.9, -14.0)],
        [(5.3, 0.6), (10.5, 0.6), (10.5, 2.5), (5.3, 2.5)],
        [(-10.4, -10.3), (8.3, -10.3), (8.3, 0.2), (-3.3, 0.2), (-3.3, 2.5), (5.0, 2.5), (5.0, 3.15), (3, 3.4), (0, 3.5), (-2, 3.45), (-3.5, 3.3), (-5, 3.05), (-7, 3.15), (-9, 3.05), (-10.4, 2.85)],
        [(0.1, -10.0), (8.1, -10.0), (8.1, -13.6), (0.1, -13.6)],
        [(9.4, -22.2), (16.6, -22.2), (16.6, -14.8), (9.4, -14.8)],
        [(7.9, -8.1), (9.1, -7.9), (9.0, -1.1), (7.9, -0.9)],
    ]
    ring = [(-3.6 + 1.15 * math.cos(a / 16 * 2 * math.pi), 7.2 + 1.15 * math.sin(a / 16 * 2 * math.pi)) for a in range(16)]
    BLOCK.append(ring)

    def density(x, z):
        if z > 24.0 or z < -44 or x < -39 or x > 44:
            return 0.0
        for poly in BLOCK:
            if pip(x, z, poly):
                return 0.0
        # thin out under the fence line and far away
        d = 1.0
        if abs(x - 9.55) < 0.12 and z < GZ - 7:
            d = 0
        far = max(0.0, (max(abs(x - 3), abs(z + 8)) - 30) / 12)
        return max(0.0, d * (1 - 0.75 * min(1, far)))

    GZ = -15.0
    me = bpy.data.meshes.new("Grass Emitter")
    bm = bmesh.new()
    step = 0.5
    xs = [(-39 + i * step) for i in range(int(83 / step) + 1)]
    zs = [(-44 + j * step) for j in range(int(68 / step) + 1)]
    grid = [[bm.verts.new(T(x, 0.004, z)) for x in xs] for z in zs]
    for j in range(len(zs) - 1):
        for i in range(len(xs) - 1):
            bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    bm.to_mesh(me)
    bm.free()
    em = bpy.data.objects.new("Grass Emitter", me)
    C_RENDER.objects.link(em)
    vg = em.vertex_groups.new(name="density")
    for v in me.vertices:
        x, z = v.co.x, -v.co.y
        w = density(x, z)
        if w > 0:
            vg.add([v.index], w, "REPLACE")
    # grass material: two greens, sun-bleached tips
    gm = bpy.data.materials.new("Grass Blades")
    gm.use_nodes = True
    g = gm.node_tree
    b = g.nodes["Principled BSDF"]
    hi = g.nodes.new("ShaderNodeHairInfo")
    ramp = g.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.05, 0.13, 0.025, 1)
    ramp.color_ramp.elements[1].color = (0.16, 0.24, 0.05, 1)
    e = ramp.color_ramp.elements.new(0.75)
    e.color = (0.09, 0.2, 0.035, 1)
    g.links.new(hi.outputs["Random"], ramp.inputs["Fac"])
    tip = g.nodes.new("ShaderNodeMix")
    tip.data_type = "RGBA"
    g.links.new(hi.outputs["Intercept"], tip.inputs["Factor"])
    g.links.new(ramp.outputs["Color"], tip.inputs[6])
    tip.inputs[7].default_value = (0.3, 0.33, 0.1, 1)
    fpow = g.nodes.new("ShaderNodeMath")
    fpow.operation = "POWER"
    g.links.new(hi.outputs["Intercept"], fpow.inputs[0])
    fpow.inputs[1].default_value = 3.0
    g.links.new(fpow.outputs[0], tip.inputs["Factor"])
    # mowed-lawn patchiness: drier, yellower patches from a large-scale noise
    tc = g.nodes.new("ShaderNodeTexCoord")
    nz = g.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.35
    nz.inputs["Detail"].default_value = 4
    g.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    pr = g.nodes.new("ShaderNodeMapRange")
    pr.inputs["From Min"].default_value = 0.45
    pr.inputs["From Max"].default_value = 0.72
    g.links.new(nz.outputs["Fac"], pr.inputs["Value"])
    dry = g.nodes.new("ShaderNodeMix")
    dry.data_type = "RGBA"
    g.links.new(pr.outputs["Result"], dry.inputs["Factor"])
    g.links.new(tip.outputs[2], dry.inputs[6])
    dry.inputs[7].default_value = (0.2, 0.22, 0.06, 1)
    g.links.new(dry.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.35
    me.materials.append(gm)
    em.modifiers.new("Grass", "PARTICLE_SYSTEM")
    ps = em.particle_systems[0]
    ps.vertex_group_density = "density"
    st = ps.settings
    st.type = "HAIR"
    st.count = 260000
    st.hair_length = 0.11
    st.emit_from = "FACE"
    st.use_emit_random = True
    st.use_even_distribution = True
    st.render_type = "PATH"
    st.display_step = 2
    st.render_step = 3
    st.use_advanced_hair = True
    st.normal_factor = 0.075
    st.factor_random = 0.025
    st.brownian_factor = 0.0
    st.use_rotations = True
    st.rotation_mode = "NOR"
    st.length_random = 0.5
    st.child_type = "INTERPOLATED"
    st.child_percent = 2
    st.rendered_child_count = 7
    st.child_radius = 0.06
    st.child_length = 1.0
    st.child_length_threshold = 0.3
    st.clump_factor = 0.15
    st.roughness_1 = 0.03
    st.roughness_1_size = 1.0
    st.roughness_endpoint = 0.05
    st.roughness_end_shape = 1.0
    st.kink = "NO"
    st.root_radius = 1.0
    st.tip_radius = 0.0
    st.radius_scale = 0.0035
    st.material_slot = "Grass Blades"
    em.show_instancer_for_render = False
    # bend: gravity-like droop via the 'roughness_2' + random tilt
    st.roughness_2 = 0.02
    st.roughness_2_size = 1.0

# ------------------------------------------------------------ cameras
VIEWS = {
    "street": ((6.5, 1.6, 19.5), (-1.2, 2.3, -3.0), 21),
    "aerial": ((22.0, 30.0, 30.0), (1.0, 0.0, -6.0), 24),
    "drive": ((12.6, 1.7, 9.5), (12.6, 1.6, -14.0), 26),
    "back": ((-9.0, 2.6, -27.5), (3.0, 1.9, -11.0), 22),
    "porch": ((-0.4, 1.6, 7.5), (-1.6, 1.7, 0.0), 28),
    "left": ((-24.0, 1.8, 12.0), (-4.0, 2.4, -2.0), 24),
}


def look(cam, pos, tgt):
    cam.location = T(*pos)
    d = T(*tgt) - T(*pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------ render settings
scene.render.engine = "CYCLES"
cy = scene.cycles
cy.device = "CPU"
cy.samples = args.samples
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.03
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 6
cy.diffuse_bounces = 3
cy.glossy_bounces = 3
cy.transmission_bounces = 4
cy.transparent_max_bounces = 12
cy.caustics_reflective = False
cy.caustics_refractive = False
scene.render.threads_mode = "AUTO"
w, h = (int(v) for v in args.res.split("x"))
scene.render.resolution_x, scene.render.resolution_y = w, h
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
scene.view_settings.exposure = 0.0

if args.save:
    cam_d = bpy.data.cameras.new("Street Camera")
    cam = bpy.data.objects.new("Street Camera", cam_d)
    C_RENDER.objects.link(cam)
    pos, tgt, lens = VIEWS["street"]
    look(cam, pos, tgt)
    cam_d.lens = lens
    scene.camera = cam
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=args.save, compress=True)
    print("saved", args.save)
    sys.exit(0)

os.makedirs(args.out, exist_ok=True)
for name in args.views.split(","):
    pos, tgt, lens = VIEWS[name]
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 8000
    cam = bpy.data.objects.new("Cam " + name, cd)
    C_RENDER.objects.link(cam)
    look(cam, pos, tgt)
    scene.camera = cam
    scene.render.filepath = os.path.join(args.out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name, flush=True)
