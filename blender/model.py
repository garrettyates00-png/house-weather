"""Yellow House: realistic Blender model of 968 Quail Chase Ln, built headless with bpy.

Layout and measurements come from the web app (yellow-house.html), which was fitted to
the owner's photos. All coordinates below are written in the app's frame
(x right as seen from the street, y up, z toward the street) and converted to Blender's
Z-up frame by T(); the glTF exporter's Y-up conversion then lands the model exactly in
the app's coordinates.

Run:  python3 model.py            -> yellow_house.blend
"""
import math
import os
import random

import bpy  # noqa: I001  (bpy must load before bmesh/mathutils)
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
random.seed(968)


def T(x, y, z):
    return Vector((x, -z, y))


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================ scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"


def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c


C_HOUSE = coll("House")
C_YARD = coll("Yard")
C_TREES = coll("Trees")
C_RENDER = coll("Render Only")


# ============================================================ materials
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexcol(h, a=1.0):
    h = h.lstrip("#")
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


_images = {}


def image(fname, non_color=False):
    key = (fname, non_color)
    if key not in _images:
        im = bpy.data.images.load(os.path.join(TEX, fname), check_existing=True)
        if non_color:
            im.colorspace_settings.name = "Non-Color"
        _images[key] = im
    return _images[key]


MAT_TILE = {}  # material name -> texture tile size (m) for world-space UVs


def material(name, color=None, tex=None, tile=1.0, rough=0.5, metal=0.0, normal=1.0,
             alpha=None, alpha_tex=False, emit=None, emit_strength=0.0, coat=0.0, spec=0.5,
             transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    inp = bsdf.inputs
    MAT_TILE[name] = tile
    if tex:
        col = nt.nodes.new("ShaderNodeTexImage")
        col.image = image(f"{tex}_col.png" if not alpha_tex else f"{tex}.png")
        col.location = (-600, 300)
        if color:  # optional tint multiply
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(col.outputs["Color"], mix.inputs[6])
            mix.inputs[7].default_value = hexcol(color)
            nt.links.new(mix.outputs[2], inp["Base Color"])
        else:
            nt.links.new(col.outputs["Color"], inp["Base Color"])
        if alpha_tex:
            nt.links.new(col.outputs["Alpha"], inp["Alpha"])
        rp = os.path.join(TEX, f"{tex}_rgh.png")
        if os.path.exists(rp):
            r = nt.nodes.new("ShaderNodeTexImage")
            r.image = image(f"{tex}_rgh.png", True)
            r.location = (-600, 0)
            nt.links.new(r.outputs["Color"], inp["Roughness"])
        else:
            inp["Roughness"].default_value = rough
        np_ = os.path.join(TEX, f"{tex}_nrm.png")
        if os.path.exists(np_):
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = image(f"{tex}_nrm.png", True)
            n.location = (-600, -300)
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = normal
            nm.location = (-300, -300)
            nt.links.new(n.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], inp["Normal"])
    else:
        inp["Base Color"].default_value = hexcol(color or "#ffffff")
        inp["Roughness"].default_value = rough
    inp["Metallic"].default_value = metal
    inp["Specular IOR Level"].default_value = spec
    if coat:
        inp["Coat Weight"].default_value = coat
        inp["Coat Roughness"].default_value = 0.05
    if transmission:
        inp["Transmission Weight"].default_value = transmission
        inp["IOR"].default_value = ior
    if alpha is not None:
        inp["Alpha"].default_value = alpha
    if alpha is not None or alpha_tex:
        try:
            m.surface_render_method = "BLENDED" if alpha is not None else "DITHERED"
        except Exception:
            pass
    if emit:
        inp["Emission Color"].default_value = hexcol(emit)
        inp["Emission Strength"].default_value = emit_strength
    return m


M = {
    "siding": material("Siding", tex="siding", tile=1.44, normal=1.0),
    "shingle": material("Shingles", tex="shingle", tile=1.0, normal=1.2, color="#c4c9cf"),
    "trim": material("Trim White", color="#f1f0e9", rough=0.38),
    "vinyl": material("Window Vinyl", color="#f4f4f0", rough=0.3),
    "glass": material("Window Glass", color="#141a20", rough=0.04, spec=0.6, metal=0.0, coat=0.0),
    "shutter": material("Shutter Green", color="#1d5a35", rough=0.45),
    "door": material("Door White", color="#efeee8", rough=0.32),
    "black": material("Black Metal", color="#141516", rough=0.35, metal=0.6),
    "foundation": material("Foundation", tex="foundation", tile=1.5),
    "concrete": material("Concrete", tex="concrete", tile=2.0),
    "drive": material("Driveway", tex="drive", tile=3.0),
    "asphalt": material("Asphalt", tex="asphalt", tile=3.0),
    "mulch": material("Mulch", tex="mulch", tile=1.0, normal=1.5),
    "fence": material("Fence Boards", tex="fence", tile=1.12),
    "rail": material("Fence Rails", tex="fence", tile=1.12, color="#a49a8c"),
    "lawn": material("Lawn Base", tex="lawn", tile=4.0),
    "paver": material("Pavers", tex="paver", tile=0.9),
    "shrub": material("Shrub Leaves", tex="shrub", tile=0.6, normal=1.6),
    "screen": material("Insect Screen", color="#1e252b", rough=0.8, alpha=0.42),
    "vent": material("Vent Louver", color="#e9e8e2", rough=0.5),
    "ventdark": material("Vent Shadow", color="#2a2c2d", rough=0.9),
    "lantern": material("Lantern Glass", color="#d9c49a", rough=0.15, emit="#ffc070", emit_strength=0.0),
    "bulb": material("Bulb", color="#e9e2cf", rough=0.3, emit="#ffcf86", emit_strength=0.0),
    "meter": material("Meter Gray", color="#a3a8ab", rough=0.4, metal=0.5),
    "bin_g": material("Bin Green", color="#2f4a35", rough=0.55),
    "bin_b": material("Bin Brown", color="#4a3328", rough=0.55),
    "paint": material("Car Paint", color="#4c5960", rough=0.25, metal=0.55, coat=1.0),
    "tire": material("Tire", color="#151617", rough=0.85),
    "rim": material("Alloy", color="#9aa1a7", rough=0.25, metal=1.0),
    "carglass": material("Car Glass", color="#0e1318", rough=0.03, spec=0.7),
    "taillight": material("Tail Light", color="#7a1418", rough=0.2, emit="#c0262c", emit_strength=0.3),
    "headlight": material("Head Light", color="#dfe4e8", rough=0.1, metal=0.3),
    "plastic": material("Trim Plastic", color="#2a2d31", rough=0.6),
    "pot": material("Terracotta", color="#a2492a", rough=0.8),
    "mumY": material("Mums Yellow", color="#e5bf2b", rough=0.7),
    "mumP": material("Mums Purple", color="#8e2d66", rough=0.7),
    "pumpkin": material("Pumpkin", color="#e06c1d", rough=0.55),
    "gourd": material("Gourd", color="#efe7d0", rough=0.6),
    "mat": material("Coir Mat", color="#9a7a4c", rough=0.95),
    "pole": material("Lamp Pole", color="#3a3d40", rough=0.5, metal=0.6),
    "lamphead": material("Lamp Head", color="#2a2c2e", rough=0.4, emit="#ffd9a8", emit_strength=0.0),
    "bark": material("Bark", tex="bark", tile=1.0, normal=1.5),
    "leaf": material("Leaves", tex="leaf_card", alpha_tex=True, rough=0.6),
    "leafEver": material("Leaves Evergreen", tex="leaf_card", alpha_tex=True, color="#7f9a74", rough=0.55),
}
# leaves: a little light through them
_l = M["leaf"].node_tree.nodes["Principled BSDF"]
for mm in (M["leaf"], M["leafEver"]):
    b = mm.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 0.0
    b.inputs["Transmission Weight"].default_value = 0.0
    try:
        b.inputs["Diffuse Roughness"].default_value = 0.5
    except KeyError:
        pass
M["glass"].node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.8


# ============================================================ mesh builder
class Builder:
    """Collects convex solids (and some open meshes) into one object, with world-space UVs."""

    def __init__(self, name, collection, bevel=0.0, bevel_segments=1, smooth=False):
        self.name, self.collection = name, collection
        self.bm = bmesh.new()
        self.mats = []
        self.bevel, self.bevel_segments, self.smooth = bevel, bevel_segments, smooth

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def solid(self, pts, faces, mats, smooth=None):
        """pts: Blender-space Vectors. faces: index lists. mats: material per face (or one).
        Faces are re-oriented to point away from the centroid (all solids here are convex)."""
        bm = self.bm
        vs = [bm.verts.new(p) for p in pts]
        cen = sum(pts, Vector()) / len(pts)
        if not isinstance(mats, (list, tuple)):
            mats = [mats] * len(faces)
        out = []
        for f, m in zip(faces, mats):
            try:
                face = bm.faces.new([vs[i] for i in f])
            except ValueError:
                continue
            face.normal_update()
            if face.normal.dot(face.calc_center_median() - cen) < 0:
                face.normal_flip()
            face.material_index = self.mi(m)
            face.smooth = self.smooth if smooth is None else smooth
            out.append(face)
        return out

    def box(self, x0, x1, y0, y1, z0, z1, mat):
        """Axis-aligned box in app coordinates."""
        P = [T(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
        # index = x + 2y + 4z
        F = [[0, 2, 6, 4], [1, 3, 7, 5], [0, 1, 5, 4], [2, 3, 7, 6], [0, 1, 3, 2], [4, 5, 7, 6]]
        return self.solid(P, F, mat)

    def corners(self, P, mat):
        """Box from 8 app-space corners ordered index = a + 2b + 4c (any parallelepiped)."""
        F = [[0, 2, 6, 4], [1, 3, 7, 5], [0, 1, 5, 4], [2, 3, 7, 6], [0, 1, 3, 2], [4, 5, 7, 6]]
        return self.solid([T(*p) for p in P], F, mat)

    def prism(self, profile, axis, s0, s1, side_mats, cap_mat):
        """Extrude a convex 2D profile along an app axis.
        axis 'x': profile pts are (z, y); axis 'z': pts are (x, y); axis 'y': pts are (x, z).
        side_mats: one material or a list per profile edge (edge i = pt i -> pt i+1)."""
        n = len(profile)

        def P(a, b, s):
            if axis == "x":
                return T(s, b, a)
            if axis == "z":
                return T(a, b, s)
            return T(a, s, b)

        pts = [P(a, b, s0) for a, b in profile] + [P(a, b, s1) for a, b in profile]
        faces = [list(range(n)), list(range(n, 2 * n))]
        mats = [cap_mat, cap_mat]
        sm = side_mats if isinstance(side_mats, (list, tuple)) else [side_mats] * n
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j, n + i])
            mats.append(sm[i])
        return self.solid(pts, faces, mats)

    def beam(self, a, b, w, h, mat, up=(0, 1, 0)):
        """Rectangular beam between app points a and b (w across, h along 'up')."""
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        u = Vector(up)
        side = d.cross(u)
        if side.length < 1e-6:
            side = d.cross(Vector((1, 0, 0)))
        side.normalize()
        u2 = side.cross(d).normalized()
        P = []
        for c in (0, 1):
            for vv in (-0.5, 0.5):
                for ss in (-0.5, 0.5):
                    base = a if c == 0 else b
                    P.append(tuple(base + side * ss * w + u2 * vv * h))
        return self.corners(P, mat)

    def cylinder(self, a, b, r0, r1, mat, seg=12, cap=True):
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        ref = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 0, 1))
        s = d.cross(ref).normalized()
        t = d.cross(s).normalized()
        ring0 = [a + (s * math.cos(k / seg * 2 * math.pi) + t * math.sin(k / seg * 2 * math.pi)) * r0 for k in range(seg)]
        ring1 = [b + (s * math.cos(k / seg * 2 * math.pi) + t * math.sin(k / seg * 2 * math.pi)) * r1 for k in range(seg)]
        pts = [T(*p) for p in ring0 + ring1]
        faces = [[k, (k + 1) % seg, seg + (k + 1) % seg, seg + k] for k in range(seg)]
        mats = [mat] * seg
        if cap:
            faces += [list(range(seg)), list(range(seg, 2 * seg))]
            mats += [mat, mat]
        fs = self.solid(pts, faces, mats, smooth=True)
        for f in fs[seg:]:
            f.smooth = False
        return fs

    def lathe(self, profile, x, y0, z, mat, seg=12):
        """Turned spindle: profile [(r, h)] around a vertical app axis at (x, z)."""
        bm = self.bm
        rings = []
        for r, h in profile:
            rings.append([bm.verts.new(T(x + r * math.cos(k / seg * 2 * math.pi), y0 + h, z + r * math.sin(k / seg * 2 * math.pi))) for k in range(seg)])
        idx = self.mi(mat)
        for a, b in zip(rings, rings[1:]):
            for k in range(seg):
                f = bm.faces.new([a[k], b[k], b[(k + 1) % seg], a[(k + 1) % seg]])
                f.material_index = idx
                f.smooth = True
        for ring, top in ((rings[0], False), (rings[-1], True)):
            f = bm.faces.new(ring if top else ring[::-1])
            f.material_index = idx
        return rings

    def flat(self, pts, y0, y1, mat, edge_mat=None):
        """Vertical extrusion of an app-space (x, z) polygon (may be concave) from y0 to y1."""
        bm = self.bm
        bot = [bm.verts.new(T(x, y0, z)) for x, z in pts]
        top = [bm.verts.new(T(x, y1, z)) for x, z in pts]
        ft = bm.faces.new(top)
        ft.normal_update()
        if ft.normal.z < 0:
            ft.normal_flip()
        ft.material_index = self.mi(mat)
        n = len(pts)
        em = self.mi(edge_mat or mat)
        area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new([bot[i], bot[j], top[j], top[i]])
            f.material_index = em
            f.normal_update()
            mid = (bot[i].co + top[j].co) / 2
            c = sum((v.co for v in top), Vector()) / n
            # outward for both windings: compare with the edge's outward normal in plan
            ex, ez = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
            out = Vector((ez, -ex)) if area > 0 else Vector((-ez, ex))  # app (x,z) outward
            if f.normal.dot(Vector((out.x, -out.y, 0))) < 0:
                f.normal_flip()
        return ft

    def finish(self):
        me = bpy.data.meshes.new(self.name)
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        uv = bm.loops.layers.uv.new("UVMap")
        names = [m.name for m in self.mats]
        Z, X = Vector((0, 0, 1)), Vector((1, 0, 0))
        for f in bm.faces:
            n = f.normal
            t = Z.cross(n)
            if t.length < 0.3:
                t = X.copy() if n.z > 0 else -X
            t.normalize()
            b = n.cross(t).normalized()
            tile = MAT_TILE.get(names[f.material_index], 1.0) if f.material_index < len(names) else 1.0
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (p.dot(t) / tile, p.dot(b) / tile)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        self.collection.objects.link(ob)
        if self.bevel:
            md = ob.modifiers.new("Bevel", "BEVEL")
            md.width = self.bevel
            md.segments = self.bevel_segments
            md.limit_method = "ANGLE"
            md.angle_limit = math.radians(40)
            md.harden_normals = False
        return ob


# ============================================================ HOUSE
FL, WT = 0.35, 3.05
house = Builder("House Shell", C_HOUSE, bevel=0.006)
trim = Builder("House Trim", C_HOUSE, bevel=0.004)
roof = Builder("Roofs", C_HOUSE)
win = Builder("Windows and Doors", C_HOUSE, bevel=0.003)
C_CUT = coll("Cutters")
cut_h = Builder("Cut House", C_CUT)
cut_g = Builder("Cut Garage", C_CUT)

# --- foundation (exposed block at the base)
house.box(-10.1, 8.1, 0, FL, -10.1, 0.05, M["foundation"])
house.box(-10.1, -3.4, 0, FL, -10.1, 1.6, M["foundation"])

# --- main body: walls extruded with the gable profile so the gable ends are real siding
# main roof underside: eave (z 0.55, y 2.98) up to ridge (z -5, y 5.36), slope 0.4288
SL_MAIN = (5.36 - 2.98) / 5.55


def main_under(z):  # roof underside height above app z
    return 5.36 - abs(z + 5) * SL_MAIN


house.prism([(0, FL), (0, main_under(0)), (-5, 5.36), (-10, main_under(-10)), (-10, FL)], "x", -6.0, 8.0,
            M["siding"], M["siding"])
# left wing (front-facing gable), roof slope 0.6167, ridge x -6.75 y 5.2, eaves x -10.35 / -3.15 at y 2.98
SL_WING = (5.2 - 2.98) / 3.6


def wing_under(x):
    return 5.2 - abs(x + 6.75) * SL_WING


house.prism([(-10, FL), (-10, wing_under(-10)), (-6.75, 5.2), (-3.5, wing_under(-3.5)), (-3.5, FL)], "z", -10.0, 1.5,
            M["siding"], M["siding"])


# --- roofs: two slabs per gable, shingle top, white underside/rake/fascia
def gable_roof(axis, e1, r, e2, s0, s1, thick=0.16, top_mat=None, under_mat=None, ridge_cap=True):
    """e1, r, e2: (a, y) eave/ridge/eave points across the roof (a = z for axis 'x', x for axis 'z')."""
    top_mat = top_mat or M["shingle"]
    under_mat = under_mat or M["trim"]
    for e in (e1, e2):
        da, dy = r[0] - e[0], r[1] - e[1]
        L = math.hypot(da, dy)
        tt = thick * L / abs(da)  # vertical thickness
        prof = [(e[0], e[1]), (r[0], r[1]), (r[0], r[1] + tt), (e[0], e[1] + tt)]
        roof.prism(prof, axis, s0, s1, [under_mat, under_mat, top_mat, under_mat], under_mat)
    if ridge_cap:  # low ridge cap shingles
        tt = thick * math.hypot(r[0] - e1[0], r[1] - e1[1]) / abs(r[0] - e1[0])
        w = 0.17
        sl = (r[1] - e1[1]) / abs(r[0] - e1[0])
        prof = [(r[0] - w, r[1] + tt - w * sl + 0.005), (r[0], r[1] + tt + 0.035), (r[0] + w, r[1] + tt - w * sl + 0.005),
                (r[0] + w, r[1] + tt - w * sl - 0.02), (r[0], r[1] + tt), (r[0] - w, r[1] + tt - w * sl - 0.02)]
        roof.prism(prof, axis, s0, s1, top_mat, M["shingle"])


gable_roof("x", (0.55, 2.98), (-5, 5.36), (-10.55, 2.98), -6.0, 8.45)
gable_roof("z", (-10.35, 2.98), (-6.75, 5.2), (-3.15, 2.98), -10.0, 1.6)


def fascia_x(x0, x1, z, y_top, out=1):
    trim.box(x0, x1, y_top - 0.2, y_top + 0.02, z - 0.03 if out > 0 else z, z if out > 0 else z + 0.03, M["trim"])


def soffit_x(x0, x1, z_wall, z_eave, y):
    trim.box(x0, x1, y - 0.03, y, min(z_wall, z_eave), max(z_wall, z_eave), M["trim"])


# main roof: back eave fascia + soffit (front eave is under the porch roof)
trim.box(-6.0, 8.45, 2.78, 3.0, -10.6, -10.55, M["trim"])
soffit_x(-6.0, 8.45, -10.0, -10.55, 2.8)
# wing eaves (left and right), fascia and soffits
trim.box(-10.4, -10.35, 2.78, 3.0, -10.0, 1.6, M["trim"])
trim.box(-10.35, -10.0, 2.77, 2.8, -10.0, 1.6, M["trim"])
trim.box(-3.15, -3.1, 2.78, 3.0, -0.2, 1.6, M["trim"])
trim.box(-3.5, -3.15, 2.77, 2.8, 0.0, 1.6, M["trim"])


# rake boards along the gable edges
def rake(a, b, out_axis, off):
    trim.beam(a, b, 0.05, 0.2, M["trim"], up=(0, 1, 0))


trim.beam((-10.38, 2.98 + 0.05, 1.63), (-6.75, 5.2 + 0.24, 1.63), 0.05, 0.22, M["trim"])
trim.beam((-6.75, 5.2 + 0.24, 1.63), (-3.12, 2.98 + 0.05, 1.63), 0.05, 0.22, M["trim"])
trim.beam((8.47, 2.98 + 0.05, 0.58), (8.47, 5.36 + 0.2, -5.0), 0.05, 0.22, M["trim"])
trim.beam((8.47, 5.36 + 0.2, -5.0), (8.47, 2.98 + 0.05, -10.58), 0.05, 0.22, M["trim"])
# rake soffits on the right gable overhang (underside is already white)

# corner boards
for x, z, sx, sz in [(-10, 1.5, -1, 1), (-3.5, 1.5, 1, 1), (8, 0, 1, 1), (-10, -10, -1, -1), (8, -10, 1, -1)]:
    trim.box(x - 0.06 if sx < 0 else x - 0.02, x + 0.02 if sx < 0 else x + 0.06, FL, WT - 0.12,
             z - 0.02 if sz > 0 else z - 0.06, z + 0.06 if sz > 0 else z + 0.02, M["trim"])
# frieze board where wall meets soffit on the wing front
trim.box(-10.0, -3.5, 2.6, 2.78, 1.5, 1.53, M["trim"])


# --- triangular louvered gable vent on the wing face
def gable_vent(xc, y_base, z_face, w=1.25, h=0.62):
    sl = h / (w / 2)
    trim.prism([(xc - w / 2 - 0.08, y_base - 0.06), (xc, y_base + h + 0.08), (xc + w / 2 + 0.08, y_base - 0.06)], "z",
               z_face, z_face + 0.03, M["trim"], M["trim"])
    trim.prism([(xc - w / 2, y_base), (xc, y_base + h), (xc + w / 2, y_base)], "z", z_face + 0.01, z_face + 0.035,
               M["ventdark"], M["ventdark"])
    for i in range(1, 9):
        y = y_base + i * h / 9.5
        half = (h - (y - y_base)) / sl
        trim.beam((xc - half + 0.02, y, z_face + 0.045), (xc + half - 0.02, y, z_face + 0.045), 0.035, 0.035, M["vent"],
                  up=(0, 0.6, 0.8))


gable_vent(-6.75, 3.95, 1.5)


# --- windows: frame generator in a wall-local frame
def frame_fn(origin, right, out):
    O, R, N, U = Vector(origin), Vector(right), Vector(out), Vector((0, 1, 0))
    return lambda u, v, d: tuple(O + R * u + U * v + N * d)


def lbox(F, b, u0, u1, v0, v1, d0, d1, mat):
    P = [F(u, v, d) for d in (d0, d1) for v in (v0, v1) for u in (u0, u1)]
    b.corners(P, mat)


def shutter(F, uc, v0, h, w=0.36):
    lbox(F, trim, uc - w / 2, uc + w / 2, v0, v0 + h, 0.0, 0.03, M["shutter"])
    mid = v0 + h * 0.48
    for a, bb in ((v0 + 0.06, mid - 0.03), (mid + 0.03, v0 + h - 0.06)):
        n = int((bb - a) / 0.055)
        for i in range(n):
            v = a + (i + 0.5) * (bb - a) / n
            P = [F(u, vv, d) for d in (0.03, 0.05) for vv in ((v - 0.02, v + 0.02) if d == 0.03 else (v - 0.025, v + 0.012)) for u in (uc - w / 2 + 0.05, uc + w / 2 - 0.05)]
            trim.corners(P, M["shutter"])


def window(F, w, h, sill, lites=(3, 2), shutters=True):
    """Double-hung window centered at u=0 on a wall frame F."""
    lbox(F, win, -w / 2, w / 2, sill, sill + h, -0.07, -0.06, M["glass"])
    fw = 0.06
    lbox(F, cut_h, -w / 2 - fw, w / 2 + fw, sill - fw, sill + h + fw, -0.1, 0.05, M["trim"])
    for u0, u1, v0, v1 in [(-w / 2 - fw, -w / 2, sill, sill + h), (w / 2, w / 2 + fw, sill, sill + h),
                           (-w / 2 - fw, w / 2 + fw, sill - fw, sill), (-w / 2 - fw, w / 2 + fw, sill + h, sill + h + fw)]:
        lbox(F, win, u0, u1, v0, v1, -0.08, 0.0, M["vinyl"])
    # sashes: meeting rail + grilles
    mid = sill + h / 2
    lbox(F, win, -w / 2, w / 2, mid - 0.03, mid + 0.03, -0.07, -0.035, M["vinyl"])
    cols, rows = lites
    for s0, s1 in ((sill, mid - 0.03), (mid + 0.03, sill + h)):
        lbox(F, win, -w / 2, w / 2, s0, s0 + 0.04, -0.07, -0.04, M["vinyl"])
        lbox(F, win, -w / 2, w / 2, s1 - 0.04, s1, -0.07, -0.04, M["vinyl"])
        for k in range(1, cols):
            u = -w / 2 + w * k / cols
            lbox(F, win, u - 0.011, u + 0.011, s0, s1, -0.062, -0.05, M["vinyl"])
        for k in range(1, rows):
            v = s0 + (s1 - s0) * k / rows
            lbox(F, win, -w / 2, w / 2, v - 0.011, v + 0.011, -0.062, -0.05, M["vinyl"])
    # casing + sill
    cw = 0.1
    lbox(F, trim, -w / 2 - fw - cw, -w / 2 - fw, sill - fw, sill + h + fw + cw, 0.0, 0.025, M["trim"])
    lbox(F, trim, w / 2 + fw, w / 2 + fw + cw, sill - fw, sill + h + fw + cw, 0.0, 0.025, M["trim"])
    lbox(F, trim, -w / 2 - fw - cw, w / 2 + fw + cw, sill + h + fw, sill + h + fw + cw, 0.0, 0.025, M["trim"])
    lbox(F, trim, -w / 2 - fw - cw - 0.03, w / 2 + fw + cw + 0.03, sill - fw - 0.05, sill - fw, -0.01, 0.06, M["trim"])
    if shutters:
        for s in (-1, 1):
            shutter(F, s * (w / 2 + fw + cw + 0.2), sill - 0.02, h + 0.1)


window(frame_fn((0.9, 0, 0.0), (1, 0, 0), (0, 0, 1)), 0.95, 1.45, 1.1)
window(frame_fn((6.3, 0, 0.0), (1, 0, 0), (0, 0, 1)), 0.95, 1.45, 1.1)
# right gable end (driveway side): double window, no shutters
window(frame_fn((8.0, 0, -6.6), (0, 0, -1), (1, 0, 0)), 1.25, 1.35, 1.1, lites=(4, 2), shutters=False)
window(frame_fn((8.0, 0, -2.0), (0, 0, -1), (1, 0, 0)), 0.75, 1.0, 1.5, lites=(2, 2), shutters=False)
# back wall windows (behind the house, facing the yard)
for x in (-8.0, -5.2):
    window(frame_fn((x, 0, -10.0), (-1, 0, 0), (0, 0, -1)), 0.95, 1.45, 1.1, shutters=False)
window(frame_fn((-10.0, 0, -4.0), (0, 0, 1), (-1, 0, 0)), 0.95, 1.45, 1.1, shutters=False)
window(frame_fn((-10.0, 0, -1.0), (0, 0, 1), (-1, 0, 0)), 0.95, 1.45, 1.1, shutters=False)


def arch_outline(w, h_rect, sill, off, n=14):
    r = w / 2 + off
    pts = [(-r, sill - off), (r, sill - off)]
    top = sill + h_rect
    for k in range(n + 1):
        a = k / n * math.pi
        pts.append((r * math.cos(a), top + r * math.sin(a)))
    pts.append((-r, sill - off))
    return pts[:-1]


def arch_window(F, w=0.9, h_rect=1.8, sill=0.95):
    top = sill + h_rect
    r = w / 2
    ro = r + 0.06
    outline = [(-ro, sill - 0.06), (ro, sill - 0.06)] + [(ro * math.cos(k / 14 * math.pi), top + ro * math.sin(k / 14 * math.pi)) for k in range(15)]
    pts = [F(u, v, d) for d in (-0.1, 0.05) for u, v in outline]
    nn = len(outline)
    faces = [list(range(nn)), list(range(nn, 2 * nn))] + [[i, (i + 1) % nn, nn + (i + 1) % nn, nn + i] for i in range(nn)]
    cut_h.solid([T(*p) for p in pts], faces, M["trim"])
    # glass: rect + half disc
    lbox(F, win, -r, r, sill, top, -0.07, -0.06, M["glass"])
    n = 14
    for k in range(n):
        a0, a1 = k / n * math.pi, (k + 1) / n * math.pi
        P = []
        for d in (-0.07, -0.06):
            for p in ((0, top), (r * math.cos(a0), top + r * math.sin(a0)), (r * math.cos(a1), top + r * math.sin(a1)), (0, top)):
                P.append(F(p[0], p[1], d))
        # wedge as degenerate box (two coincident verts at the center)
        win.solid([T(*p) for p in P[:3] + P[4:7]], [[0, 1, 2], [3, 4, 5], [0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5]], M["glass"])
    # frame ring (vinyl) and casing ring (trim) built from quads around the outline
    for (o0, o1, d0, d1, mat, b) in ((0.0, 0.06, -0.08, 0.0, M["vinyl"], win), (0.06, 0.16, 0.0, 0.025, M["trim"], trim)):
        for k in range(n):
            a0, a1 = k / n * math.pi, (k + 1) / n * math.pi
            P = []
            for d in (d0, d1):
                for (rr, a) in ((r + o0, a0), (r + o0, a1), (r + o1, a0), (r + o1, a1)):
                    P.append(F(rr * math.cos(a), top + rr * math.sin(a), d))
            b.corners([P[0], P[1], P[2], P[3], P[4], P[5], P[6], P[7]], mat)
        lbox(F, b, -r - o1, -r - o0, sill - o1 if b is win else sill - 0.06, top, d0, d1, mat)
        lbox(F, b, r + o0, r + o1, sill - o1 if b is win else sill - 0.06, top, d0, d1, mat)
    lbox(F, win, -r, r, sill - 0.06, sill, -0.08, 0.0, M["vinyl"])
    lbox(F, trim, -r - 0.19, r + 0.19, sill - 0.11, sill - 0.06, -0.01, 0.06, M["trim"])
    # grilles: 2x3 lower lites, sunburst in the arch
    lbox(F, win, -0.011, 0.011, sill, top + r, -0.062, -0.05, M["vinyl"])
    for k in (1, 2):
        v = sill + h_rect * k / 3
        lbox(F, win, -r, r, v - 0.011, v + 0.011, -0.062, -0.05, M["vinyl"])
    lbox(F, win, -r, r, top - 0.015, top + 0.015, -0.062, -0.05, M["vinyl"])
    for a in (math.pi / 4, 3 * math.pi / 4):
        p0, p1 = (0, top), (r * math.cos(a), top + r * math.sin(a))
        win.beam(F(p0[0], p0[1], -0.056), F(p1[0], p1[1], -0.056), 0.022, 0.012, M["vinyl"], up=tuple(Vector(F(0, 0, 1)) - Vector(F(0, 0, 0))))
    for s in (-1, 1):
        shutter(F, s * (r + 0.36), sill - 0.02, h_rect + 0.05, w=0.34)


for x in (-8.2, -5.3):
    arch_window(frame_fn((x, 0, 1.5), (1, 0, 0), (0, 0, 1)))

# --- front door (9-lite over 2 raised panels), casing, hardware
F = frame_fn((-1.75, 0, 0.0), (1, 0, 0), (0, 0, 1))
lbox(F, win, -0.48, 0.48, FL, FL + 2.05, -0.04, 0.0, M["door"])
lbox(F, cut_h, -0.48, 0.48, FL - 0.01, FL + 2.05, -0.1, 0.05, M["door"])
for u0, u1, v0, v1 in [(-0.58, -0.48, FL, FL + 2.15), (0.48, 0.58, FL, FL + 2.15), (-0.58, 0.58, FL + 2.05, FL + 2.17)]:
    lbox(F, trim, u0, u1, v0, v1, 0.0, 0.03, M["trim"])
gx0, gx1, gy0, gy1 = -0.34, 0.34, FL + 1.12, FL + 1.88
lbox(F, win, gx0, gx1, gy0, gy1, 0.0, 0.004, M["glass"])
for k in (1, 2):
    u = lerp(gx0, gx1, k / 3)
    lbox(F, win, u - 0.012, u + 0.012, gy0, gy1, 0.004, 0.018, M["door"])
    v = lerp(gy0, gy1, k / 3)
    lbox(F, win, gx0, gx1, v - 0.012, v + 0.012, 0.004, 0.018, M["door"])
for u0, u1, v0, v1 in [(gx0 - 0.03, gx0, gy0 - 0.03, gy1 + 0.03), (gx1, gx1 + 0.03, gy0 - 0.03, gy1 + 0.03),
                       (gx0, gx1, gy0 - 0.03, gy0), (gx0, gx1, gy1, gy1 + 0.03)]:
    lbox(F, win, u0, u1, v0, v1, 0.0, 0.02, M["door"])
for u0, u1 in ((-0.36, -0.04), (0.04, 0.36)):
    lbox(F, win, u0, u1, FL + 0.2, FL + 0.95, 0.0, 0.012, M["door"])
    lbox(F, win, u0 + 0.04, u1 - 0.04, FL + 0.24, FL + 0.91, 0.012, 0.022, M["door"])
lbox(F, win, 0.36, 0.4, FL + 0.88, FL + 1.12, 0.0, 0.05, M["black"])  # handle
for v in (FL + 0.3, FL + 1.0, FL + 1.75):
    lbox(F, win, -0.47, -0.36, v, v + 0.12, 0.0, 0.01, M["black"])  # hinges
lbox(F, win, 0.66, 0.73, FL + 1.2, FL + 1.36, 0.0, 0.03, M["black"])  # video doorbell
lbox(F, trim, -1.07, -0.97, FL + 1.18, FL + 1.3, 0.0, 0.02, M["trim"])  # switch plate area
# coir mat
win.box(-2.15, -1.35, FL, FL + 0.015, 0.1, 0.62, M["mat"])
# lantern beside the door
win.box(-1.02, -0.88, 1.88, 2.18, 0.03, 0.17, M["black"])
win.box(-1.0, -0.9, 1.91, 2.12, 0.05, 0.15, M["lantern"])
win.box(-1.04, -0.86, 2.18, 2.21, 0.01, 0.19, M["black"])

# --- front porch: slab, shed roof, posts, rails, balusters, step
house.box(-3.4, 4.95, 0, FL, 0, 2.45, M["concrete"])
porch_sl = (3.02 - 2.66) / 2.3
roof.prism([(0.0, 3.02 + 0.0 * porch_sl), (2.7, 2.66), (2.7, 2.66 + 0.13), (0.0, 3.02 + 0.13 + 0.4 * porch_sl)], "x",
           -3.5, 5.05, [M["trim"], M["trim"], M["shingle"], M["trim"]], M["trim"])
trim.box(-3.5, 5.05, 2.48, 2.7, 2.69, 2.73, M["trim"])  # porch fascia
trim.box(-3.4, 4.95, 2.47, 2.5, 0.0, 2.69, M["trim"])  # porch ceiling (flat, beadboard white)
trim.box(-3.4, 4.95, 2.32, 2.5, 2.22, 2.4, M["trim"])  # beam over the posts
POSTS = [-3.25, -0.45, 2.2, 4.8]
for x in POSTS:
    trim.box(x - 0.07, x + 0.07, FL, 2.32, 2.23, 2.37, M["trim"])
    trim.box(x - 0.1, x + 0.1, FL, FL + 0.28, 2.2, 2.4, M["trim"])
    trim.box(x - 0.1, x + 0.1, 2.2, 2.32, 2.2, 2.4, M["trim"])
bal = Builder("Porch Balusters", C_HOUSE, smooth=True)
BAL = [(0.024, 0), (0.024, 0.07), (0.03, 0.08), (0.036, 0.11), (0.021, 0.2), (0.03, 0.36), (0.018, 0.52), (0.027, 0.62),
       (0.02, 0.7), (0.024, 0.72), (0.024, 0.76)]


def rail_run(x0, z0, x1, z1):
    trim.beam((x0, FL + 0.86, z0), (x1, FL + 0.86, z1), 0.08, 0.05, M["trim"])
    trim.beam((x0, FL + 0.08, z0), (x1, FL + 0.08, z1), 0.06, 0.05, M["trim"])
    L = math.hypot(x1 - x0, z1 - z0)
    n = int(L / 0.13)
    for i in range(1, n):
        t = i / n
        bal.lathe(BAL, lerp(x0, x1, t), FL + 0.1, lerp(z0, z1, t), M["trim"], seg=8)


rail_run(-3.17, 2.3, -0.53, 2.3)
rail_run(-0.37, 2.3, 2.12, 2.3)
rail_run(2.28, 2.3, 4.72, 2.3)
rail_run(-3.25, 0.1, -3.25, 2.22)
house.box(4.95, 5.4, 0, 0.18, 1.15, 2.3, M["concrete"])

# --- chimney chase (siding box on the back slope) with cap and flue
house.box(-0.4, 1.0, 3.4, 6.5, -8.9, -7.5, M["siding"])
for x, z in [(-0.4, -8.9), (1.0, -8.9), (-0.4, -7.5), (1.0, -7.5)]:
    trim.box(x - 0.05, x + 0.05, 3.4, 6.5, z - 0.05, z + 0.05, M["trim"])
trim.box(-0.48, 1.08, 6.5, 6.6, -8.98, -7.42, M["trim"])
trim.box(-0.3, 0.9, 6.6, 6.66, -8.8, -7.6, M["black"])
trim.cylinder((0.3, 6.6, -8.2), (0.3, 7.0, -8.2), 0.15, 0.15, M["black"], seg=16)
trim.cylinder((0.3, 7.0, -8.2), (0.3, 7.08, -8.2), 0.22, 0.05, M["black"], seg=16)

# --- right gable end: louvered vent, meters, gas line, bollards
F = frame_fn((8.0, 0, -5.0), (0, 0, -1), (1, 0, 0))
lbox(F, trim, -0.85, 0.85, 4.15, 4.95, 0.0, 0.04, M["trim"])
lbox(F, trim, -0.75, 0.75, 4.22, 4.88, 0.04, 0.045, M["ventdark"])
for i in range(9):
    v = 4.26 + i * 0.07
    P = [F(u, vv, d) for d in (0.03, 0.08) for vv in ((v, v + 0.05) if d == 0.03 else (v - 0.01, v + 0.03)) for u in (-0.74, 0.74)]
    trim.corners(P, M["vent"])
house.box(8.0, 8.18, 0.92, 1.62, -4.95, -4.45, M["meter"])
house.box(8.0, 8.24, 0.25, 0.75, -3.25, -2.85, M["meter"])
trim.cylinder((8.15, 0.0, -2.75), (8.15, 0.8, -2.75), 0.03, 0.03, M["meter"], seg=8)
for z in (-3.7, -2.2):
    trim.cylinder((8.75, 0, z), (8.75, 1.05, z), 0.075, 0.075, M["trim"], seg=16)

# --- gutters and downspouts
def gutter_x(x0, x1, z, y, back=False):
    s = -1 if back else 1
    trim.box(x0, x1, y - 0.13, y - 0.11, min(z, z + s * 0.13), max(z, z + s * 0.13), M["trim"])
    trim.box(x0, x1, y - 0.13, y, z + s * 0.11 if not back else z - 0.13, z + s * 0.13 if not back else z - 0.11, M["trim"])
    trim.box(x0, x1, y - 0.13, y - 0.02, min(z, z + s * 0.01), max(z, z + s * 0.01), M["trim"])


gutter_x(-6.0, 8.45, -10.58, 2.98, back=True)
for x, z in [(8.12, 0.12), (8.12, -10.12), (-10.12, -10.12), (-10.12, 1.62), (-3.38, 1.62)]:
    trim.box(x - 0.045, x + 0.045, 0.1, 2.92, z - 0.035, z + 0.035, M["trim"])
    trim.box(x - 0.05, x + 0.05, 0.0, 0.08, z - 0.2, z + 0.2, M["concrete"])  # splash block

# --- screened back porch
house.box(0.2, 8.0, 0, 0.3, -13.45, -10, M["concrete"])
house.box(0.2, 8.0, 0.3, 0.95, -13.45, -13.33, M["siding"])
house.box(0.2, 0.32, 0.3, 0.95, -13.45, -10, M["siding"])
house.box(7.88, 8.0, 0.3, 0.95, -13.45, -11.45, M["siding"])
x = 0.2
while x <= 8.01:
    trim.box(x - 0.06, x + 0.06, 0.3, 2.5, -13.47, -13.33, M["trim"])
    x += 1.3
for z in (-11.45, -12.45):
    trim.box(0.18, 0.32, 0.3, 2.5, z - 0.06, z + 0.06, M["trim"])
    trim.box(7.88, 8.02, 0.3, 2.5, z - 0.06, z + 0.06, M["trim"])
trim.box(0.2, 8.0, 0.95, 1.02, -13.47, -13.33, M["trim"])
trim.box(0.2, 8.0, 2.42, 2.5, -13.47, -13.33, M["trim"])
scr = Builder("Screens", C_HOUSE)
scr.box(0.2, 8.0, 1.02, 2.42, -13.4, -13.39, M["screen"])
scr.box(0.25, 0.26, 1.02, 2.42, -13.4, -10.05, M["screen"])
scr.box(7.94, 7.95, 1.02, 2.42, -13.4, -11.5, M["screen"])
scr.box(7.97, 7.98, 0.32, 2.36, -11.24, -10.26, M["screen"])  # screen door
for z0, z1 in ((-10.3, -10.24), (-11.26, -11.2)):
    trim.box(7.96, 8.04, 0.3, 2.38, z0, z1, M["trim"])
trim.box(7.96, 8.04, 2.32, 2.38, -11.26, -10.24, M["trim"])
trim.box(7.96, 8.04, 1.0, 1.06, -11.26, -10.24, M["trim"])
bp_sl = (3.0 - 2.55) / 3.75
roof.prism([(-10.0, 3.0), (-13.75, 2.55), (-13.75, 2.68), (-10.0, 3.13)], "x", 0.05, 8.2,
           [M["trim"], M["trim"], M["shingle"], M["trim"]], M["trim"])
trim.box(0.05, 8.2, 2.36, 2.56, -13.8, -13.75, M["trim"])
trim.box(0.2, 8.0, 2.47, 2.5, -13.45, -10.0, M["trim"])  # ceiling
gutter_x(0.05, 8.2, -13.8, 2.56, back=True)
bulbs = Builder("String Lights", C_HOUSE, smooth=True)
for i in range(12):
    x = 0.6 + i * 0.62
    y = 2.3 - math.sin((i % 3) / 2 * math.pi) * 0.07
    bulbs.cylinder((x, y - 0.05, -13.25), (x, y + 0.05, -13.25), 0.035, 0.035, M["bulb"], seg=8)

# --- porch decor: mums, pumpkins
deco = Builder("Porch Decor", C_HOUSE, smooth=True)


def blob(b, cx, cy, cz, r, mat, sy=1.0, seg=12, rings=8, bumps=0.0):
    bm = b.bm
    idx = b.mi(mat)
    vs = []
    for i in range(rings + 1):
        th = i / rings * math.pi
        row = []
        for k in range(seg):
            ph = k / seg * 2 * math.pi
            rr = r * (1 + bumps * math.sin(ph * 8) * math.sin(th) if bumps else 1)
            row.append(bm.verts.new(T(cx + rr * math.sin(th) * math.cos(ph), cy + r * sy * math.cos(th), cz + rr * math.sin(th) * math.sin(ph))))
        vs.append(row)
    for i in range(rings):
        for k in range(seg):
            a, bq, c, d = vs[i][k], vs[i][(k + 1) % seg], vs[i + 1][(k + 1) % seg], vs[i + 1][k]
            try:
                f = bm.faces.new([a, bq, c, d])
            except ValueError:
                continue
            f.material_index = idx
            f.smooth = True
    return vs


blob(deco, -2.95, FL + 0.42, 0.45, 0.3, M["mumY"], sy=0.85)
blob(deco, -2.4, FL + 0.46, 0.35, 0.3, M["mumP"], sy=0.85)
deco.box(-3.12, -2.78, FL, FL + 0.22, 0.28, 0.62, M["pot"])
deco.box(-2.57, -2.23, FL, FL + 0.22, 0.18, 0.52, M["pot"])
blob(deco, -0.95, FL + 0.17, 0.42, 0.2, M["pumpkin"], sy=0.82, bumps=0.06)
blob(deco, -0.7, FL + 0.08, 0.6, 0.1, M["gourd"], sy=0.7, bumps=0.08)
blob(deco, -0.55, FL + 0.08, 0.38, 0.1, M["pumpkin"], sy=0.75, bumps=0.08)

# --- garage (detached, set back on the right)
GZ = -15.0
SL_G = (4.2 - 2.72) / 3.8


def g_under(z):
    return 4.2 - abs(z - (GZ - 3.5)) * SL_G


gar = Builder("Garage", C_HOUSE, bevel=0.006)
gar.box(9.55, 16.45, 0, 0.15, GZ - 7.05, GZ + 0.05, M["foundation"])
gar.prism([(GZ, 0.15), (GZ, g_under(GZ)), (GZ - 3.5, 4.2), (GZ - 7, g_under(GZ - 7)), (GZ - 7, 0.15)], "x", 9.6, 16.4,
          M["siding"], M["siding"])
gable_roof("x", (GZ + 0.3, 2.72), (GZ - 3.5, 4.2), (GZ - 7.3, 2.72), 9.3, 16.7, thick=0.14)
trim.box(9.3, 16.7, 2.52, 2.74, GZ + 0.3, GZ + 0.33, M["trim"])
trim.box(9.3, 16.7, 2.52, 2.74, GZ - 7.33, GZ - 7.3, M["trim"])
soffit_x(9.3, 16.7, GZ, GZ + 0.3, 2.54)
soffit_x(9.3, 16.7, GZ - 7.3, GZ - 7.0, 2.54)
gutter_x(9.3, 16.7, GZ + 0.33, 2.74)
for x in (9.27, 16.73):
    trim.beam((x, 2.74, GZ + 0.33), (x, 4.2 + 0.18, GZ - 3.5), 0.05, 0.2, M["trim"])
    trim.beam((x, 4.2 + 0.18, GZ - 3.5), (x, 2.74, GZ - 7.33), 0.05, 0.2, M["trim"])
for x, z in [(9.6, GZ), (16.4, GZ), (9.6, GZ - 7), (16.4, GZ - 7)]:
    trim.box(x - 0.06, x + 0.06, 0.15, 2.6, z - 0.06, z + 0.06, M["trim"])
# sectional door: 4 panels with grooves, plus jamb trim
F = frame_fn((13.0, 0, GZ), (1, 0, 0), (0, 0, 1))
for i in range(4):
    v0 = 0.04 + i * 0.53
    lbox(F, gar, -2.45, 2.45, v0 + 0.006, v0 + 0.524, -0.03, 0.0, M["door"])
    for k in range(4):
        u0 = -2.4 + k * 1.21
        lbox(F, gar, u0 + 0.06, u0 + 1.15, v0 + 0.09, v0 + 0.44, 0.0, 0.012, M["door"])
lbox(F, gar, -2.45, 2.45, 0.0, 2.17, -0.05, -0.04, M["ventdark"])
lbox(F, cut_g, -2.45, 2.45, 0.05, 2.17, -0.1, 0.05, M["door"])
for u0, u1, v1 in [(-2.6, -2.45, 2.3), (2.45, 2.6, 2.3)]:
    lbox(F, trim, u0, u1, 0.0, v1, 0.0, 0.03, M["trim"])
lbox(F, trim, -2.6, 2.6, 2.17, 2.3, 0.0, 0.03, M["trim"])
lbox(F, trim, -3.05, -2.85, 1.75, 2.1, 0.0, 0.12, M["black"])  # coach light
lbox(F, trim, -3.01, -2.89, 1.8, 2.03, 0.05, 0.13, M["lantern"])
# side door on the garage's yard side
F = frame_fn((9.6, 0, GZ - 4.5), (0, 0, 1), (-1, 0, 0))
lbox(F, win, -0.45, 0.45, 0.15, 2.15, -0.03, 0.0, M["door"])
lbox(F, cut_g, -0.45, 0.45, 0.16, 2.15, -0.1, 0.05, M["door"])
lbox(F, trim, -0.55, 0.55, 2.15, 2.25, 0.0, 0.03, M["trim"])
for s in (-1, 1):
    lbox(F, trim, s * 0.45 - (0.1 if s < 0 else 0), s * 0.45 + (0.1 if s > 0 else 0), 0.15, 2.15, 0.0, 0.03, M["trim"])
lbox(F, win, 0.3, 0.36, 1.0, 1.08, 0.0, 0.05, M["black"])

for b in (trim, roof, win, bal, scr, bulbs, deco):
    b.finish()
for b, c in ((house, cut_h), (gar, cut_g)):
    ob = b.finish()
    co = c.finish()
    co.hide_render = True
    co.display_type = "WIRE"
    md = ob.modifiers.new("Openings", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.object = co
    md.solver = "EXACT"
    md.use_self = True
    md.use_hole_tolerant = True
    ob.modifiers.move(len(ob.modifiers) - 1, 0)

# ============================================================ YARD
yard = Builder("Hardscape", C_YARD, bevel=0.01)
yard.flat([(9.6, -15), (16.4, -15), (16.4, -9.4), (14.6, -8.2), (13.9, -7.2), (13.9, 22.8), (14.9, 24.3), (9.4, 24.3),
           (10.4, 22.8), (10.4, -7.6), (9.6, -8.6)], -0.05, 0.03, M["drive"])
yard.flat([(8.0, -10.1), (9.7, -10.1), (9.7, -13.9), (8.0, -13.9)], -0.05, 0.028, M["concrete"])
yard.flat([(5.4, 1.5), (10.4, 1.5), (10.4, 2.4), (5.4, 2.4)], -0.05, 0.025, M["paver"])
yard.flat([(5.4, 0.7), (8.0, 0.7), (8.0, 1.5), (5.4, 1.5)], -0.05, 0.02, M["concrete"])
# driveway control joints
for z in (-1.0, 6.0, 13.0, 19.0):
    yard.box(10.4, 13.9, 0.029, 0.033, z - 0.008, z + 0.008, M["plastic"])
# street + curb
yard.flat([(-60, 24.45), (60, 24.45), (60, 34), (-60, 34)], -0.1, 0.0, M["asphalt"])
yard.box(-60, 9.4, -0.1, 0.12, 24.1, 24.45, M["concrete"])
yard.box(14.9, 60, -0.1, 0.12, 24.1, 24.45, M["concrete"])
yard.box(9.4, 14.9, -0.1, 0.03, 24.1, 24.45, M["concrete"])

# mulch beds (raised slightly) with black edging
beds = Builder("Mulch Beds", C_YARD)
for pts in ([(-10.35, 1.5), (-3.4, 1.5), (-3.4, 2.45), (-3.5, 2.75), (-5, 3.0), (-7, 3.1), (-9, 3.0), (-10.35, 2.8)],
            [(-3.4, 2.45), (4.95, 2.45), (4.95, 3.1), (3, 3.35), (0, 3.45), (-2, 3.4), (-3.4, 3.2)],
            [(8.0, -8.0), (8.0, -1.0), (8.9, -1.2), (9.0, -7.8)]):
    beds.flat(pts, -0.05, 0.06, M["mulch"], edge_mat=M["plastic"])
# front lawn ring around the big tree
ring = [(-3.6 + 1.1 * math.cos(a / 16 * 2 * math.pi), 7.2 + 1.1 * math.sin(a / 16 * 2 * math.pi)) for a in range(16)]
beds.flat(ring, -0.05, 0.05, M["mulch"], edge_mat=M["plastic"])

# lawn ground: lot plus surroundings
lawn = Builder("Lawn", C_YARD)
lawn.flat([(-40, -45), (45, -45), (45, 24.1), (-40, 24.1)], -0.2, 0.0, M["lawn"])
lawn.flat([(-60, 34), (60, 34), (60, 70), (-60, 70)], -0.2, 0.0, M["lawn"])
far = Builder("Far Ground", C_RENDER)
far.flat([(-4000, -4000), (4000, -4000), (4000, 4000), (-4000, 4000)], -0.4, -0.02, M["lawn"])

# shrubs: lumpy boxwood mounds
shr = Builder("Shrubs", C_YARD, smooth=True)
SHRUBS = [(-9.2, 2.0, 1.0), (-7.4, 2.05, 1.0), (-6.0, 2.0, 1.0), (-4.3, 2.0, 1.0), (-2.4, 2.95, 0.7), (-0.4, 3.0, 0.65),
          (1.8, 2.95, 0.7), (3.8, 2.85, 0.6), (8.45, -7.2, 0.6), (8.45, -5.8, 0.55), (8.45, -1.7, 0.55)]
for x, z, k in SHRUBS:
    r = 0.62 * k
    bm = shr.bm
    idx = shr.mi(M["shrub"])
    rows = []
    seg, rn = 18, 10
    ph0 = random.random() * 6
    for i in range(rn + 1):
        th = i / rn * math.pi * 0.62  # cut off below: sits on the bed
        row = []
        for j in range(seg):
            ph = j / seg * 2 * math.pi
            n = 1 + 0.07 * math.sin(3 * ph + ph0) * math.sin(2 * th + 1) + 0.05 * math.sin(5 * ph + 2 * th + ph0)
            rx, ry = r * 1.25 * n, r * 0.95 * n
            row.append(bm.verts.new(T(x + rx * math.sin(th) * math.cos(ph), 0.04 + ry * (math.cos(th) - math.cos(math.pi * 0.62)), z + rx * 0.85 * math.sin(th) * math.sin(ph))))
        rows.append(row)
    top = bm.verts.new(T(x, 0.04 + r * 0.95 * (1 - math.cos(math.pi * 0.62)) + r * 0.02, z))
    for j in range(seg):
        f = bm.faces.new([top, rows[1][(j + 1) % seg], rows[1][j]])
        f.material_index, f.smooth = idx, True
    for i in range(1, rn):
        for j in range(seg):
            f = bm.faces.new([rows[i][j], rows[i][(j + 1) % seg], rows[i + 1][(j + 1) % seg], rows[i + 1][j]])
            f.material_index, f.smooth = idx, True
bm = shr.bm
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# fence: 6 ft board-on-board privacy fence with gates, posts and rails on the yard side
fen = Builder("Fence", C_YARD, bevel=0.005)
FH = 1.85


def fence_run(x0, z0, x1, z1, gate=None):
    along_x = abs(x1 - x0) > abs(z1 - z0)
    a0, a1 = (min(x0, x1), max(x0, x1)) if along_x else (min(z0, z1), max(z0, z1))
    c = z0 if along_x else x0

    def seg(s0, s1):
        if s1 - s0 < 0.05:
            return
        if along_x:
            fen.box(s0, s1, 0.04, FH, c - 0.025, c + 0.025, M["fence"])
        else:
            fen.box(c - 0.025, c + 0.025, 0.04, FH, s0, s1, M["fence"])

    if gate is None:
        seg(a0, a1)
    else:
        seg(a0, gate - 0.55)
        seg(gate + 0.55, a1)
        if along_x:
            fen.box(gate - 0.52, gate + 0.52, 0.07, FH - 0.03, c + 0.03, c + 0.075, M["fence"])
        else:
            fen.box(c + 0.03, c + 0.075, 0.07, FH - 0.03, gate - 0.52, gate + 0.52, M["fence"])
    for y in (0.3, FH - 0.32):
        if along_x:
            fen.box(a0, a1, y, y + 0.09, c - 0.065, c - 0.025, M["rail"])
        else:
            fen.box(c - 0.065, c - 0.025, y, y + 0.09, a0, a1, M["rail"])
    n = max(1, round((a1 - a0) / 2.4))
    for i in range(n + 1):
        s = a0 + (a1 - a0) * i / n
        if along_x:
            fen.box(s - 0.045, s + 0.045, 0, FH + 0.08, c - 0.115, c - 0.025, M["rail"])
        else:
            fen.box(c - 0.115, c - 0.025, 0, FH + 0.08, s - 0.045, s + 0.045, M["rail"])
    # top cap
    if along_x:
        fen.box(a0, a1, FH, FH + 0.03, c - 0.06, c + 0.04, M["rail"])
    else:
        fen.box(c - 0.06, c + 0.04, FH, FH + 0.03, a0, a1, M["rail"])


fence_run(16.45, GZ - 0.05, 20.5, GZ - 0.05, 19.3)
fence_run(20.5, GZ - 0.05, 20.5, -30)
fence_run(-16.5, -30, 20.5, -30)
fence_run(-16.5, -6.2, -16.5, -30)
fence_run(-16.5, -6.2, -10.05, -6.2, -13)
fence_run(8.05, -14.0, 9.55, -14.0)
fence_run(9.55, GZ - 7.05, 9.55, -30)

# trash bins, mailbox, street lamps
misc = Builder("Yard Items", C_YARD, bevel=0.02, bevel_segments=2)
for x, m in ((16.95, M["bin_g"]), (17.75, M["bin_b"])):
    misc.box(x - 0.32, x + 0.32, 0.0, 1.02, GZ + 0.27, GZ + 0.93, m)
    misc.box(x - 0.37, x + 0.37, 1.02, 1.1, GZ + 0.22, GZ + 0.98, m)
    for s in (-1, 1):
        misc.cylinder((x + s * 0.28, 0.1, GZ + 0.98), (x + s * 0.34, 0.1, GZ + 0.98), 0.1, 0.1, M["tire"], seg=12)
misc.box(8.6, 8.7, 0, 1.05, 23.38, 23.48, M["trim"])
misc.box(8.45, 8.85, 1.05, 1.3, 23.15, 23.72, M["black"])
for x, z in ((-15, 25.3), (21, 25.3), (-12, 33.6)):
    zf = 1 if z < 30 else -1
    misc.cylinder((x, 0, z), (x, 6.2, z), 0.1, 0.07, M["pole"], seg=12)
    misc.box(x - 0.04, x + 0.04, 6.06, 6.14, min(z, z + zf * 1.5), max(z, z + zf * 1.5), M["pole"])
    misc.box(x - 0.21, x + 0.21, 5.95, 6.09, z + zf * 1.15, z + zf * 1.85, M["lamphead"])


# SUV on the pad, nose to the garage: generic blue-gray compact crossover (no badges)
car = Builder("SUV", C_YARD, bevel=0.06, bevel_segments=3)
cx, cz = 12.9, -11.9
fr, rr = cz - 2.25, cz + 2.25
car.box(cx - 0.91, cx + 0.91, 0.36, 0.98, fr + 0.15, rr - 0.08, M["paint"])
car.prism([(fr, 0.42), (fr + 0.15, 0.98), (fr + 1.15, 1.04), (fr + 1.15, 0.42)], "x", cx - 0.89, cx + 0.89, M["paint"], M["paint"])
car.prism([(rr - 0.08, 0.98), (rr - 0.45, 1.62), (fr + 1.95, 1.66), (fr + 1.15, 1.02)], "x", cx - 0.79, cx + 0.79, M["carglass"], M["carglass"])
car.box(cx - 0.8, cx + 0.8, 1.62, 1.7, fr + 1.9, rr - 0.47, M["paint"])
for z in (rr - 0.33, cz + 0.05, fr + 1.55):
    car.box(cx - 0.8, cx + 0.8, 1.0, 1.64, z - 0.06, z + 0.06, M["paint"])
car.box(cx - 0.92, cx + 0.92, 0.3, 0.55, rr - 0.12, rr + 0.03, M["plastic"])
car.box(cx - 0.92, cx + 0.92, 0.3, 0.5, fr - 0.03, fr + 0.16, M["plastic"])
car.box(cx - 0.93, cx + 0.93, 0.3, 0.45, fr + 0.2, rr - 0.15, M["plastic"])  # cladding
for sx in (-1, 1):
    car.box(cx + sx * 0.7 - 0.22, cx + sx * 0.7 + 0.22, 0.8, 0.92, rr - 0.04, rr + 0.02, M["taillight"])
    car.box(cx + sx * 0.66 - 0.2, cx + sx * 0.66 + 0.2, 0.74, 0.84, fr - 0.01, fr + 0.06, M["headlight"])
    car.box(cx + sx * 0.97 - 0.07, cx + sx * 0.97 + 0.07, 1.0, 1.12, fr + 1.25, fr + 1.42, M["paint"])
    car.box(cx + sx * 0.6 - 0.03, cx + sx * 0.6 + 0.03, 1.7, 1.75, fr + 2.0, rr - 0.6, M["plastic"])
wheels = Builder("SUV Wheels", C_YARD, smooth=True)
for sx in (-1, 1):
    for z in (fr + 0.85, rr - 0.9):
        wheels.cylinder((cx + sx * 0.72, 0.36, z), (cx + sx * 0.96, 0.36, z), 0.36, 0.36, M["tire"], seg=24)
        wheels.cylinder((cx + sx * 0.955, 0.36, z), (cx + sx * 0.965, 0.36, z), 0.22, 0.22, M["rim"], seg=24)

for b in (yard, beds, lawn, far, shr, fen, misc, car, wheels):
    b.finish()


# ============================================================ TREES (render only; the app animates its own)
def make_tree(name, x, z, trunk, r, forks, angle0, length, depth, branch, angle, lift, lenF, per, clump, card, ever=False,
              seed=0):
    rnd = random.Random(seed)
    bark = Builder(name + " Wood", C_TREES, smooth=True)
    tips = []

    def rdir(base, spread, lift_):
        d = Vector(base)
        axis = Vector((rnd.uniform(-1, 1), 0, rnd.uniform(-1, 1))).normalized()
        d.rotate(Matrix.Rotation(math.radians(rnd.uniform(spread * 0.6, spread)), 3, axis))
        d.y += lift_
        return d.normalized()

    def grow(start, d, L, rad, dep):
        end = start + d * L
        bark.cylinder(start, end, rad, rad * 0.68, M["bark"], seg=8, cap=False)
        if dep == 0:
            tips.append(end)
            # twigs
            for _ in range(3):
                tdir = rdir(d, 50, 0.2)
                bark.cylinder(end, end + tdir * L * 0.5, rad * 0.6, rad * 0.2, M["bark"], seg=5, cap=False)
            return
        n = branch + (1 if rnd.random() < 0.35 else 0)
        for i in range(n):
            s = end if i == 0 else end.lerp(start, rnd.uniform(0, 0.35))
            grow(s, rdir(d, angle, lift), L * lenF * rnd.uniform(0.85, 1.1), rad * 0.62, dep - 1)

    base = Vector((x, 0, z))
    top = base + Vector((rnd.uniform(-0.2, 0.2), trunk, rnd.uniform(-0.2, 0.2)))
    bark.cylinder(base - Vector((0, 0.1, 0)), top, r * 1.15, r * 0.78, M["bark"], seg=12, cap=False)
    # root flare
    for k in range(5):
        a = k / 5 * 2 * math.pi + rnd.uniform(0, 0.5)
        bark.cylinder(base + Vector((math.cos(a) * r * 0.5, 0.35, math.sin(a) * r * 0.5)),
                      base + Vector((math.cos(a) * r * 1.9, -0.05, math.sin(a) * r * 1.9)), r * 0.45, r * 0.15, M["bark"], seg=6, cap=False)
    for i in range(forks):
        grow(top, rdir(Vector((0, 1, 0)), angle0, 0.4), length, r * 0.7, depth)
    bark.finish()
    # leaf cards around each tip, oriented randomly, biased outward from the crown center
    leaves = Builder(name + " Leaves", C_TREES)
    crown = sum(tips, Vector()) / max(1, len(tips))
    bm = leaves.bm
    idx = leaves.mi(M["leafEver"] if ever else M["leaf"])
    uvl = []
    for p in tips:
        for i in range(per):
            v = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.7, 1), rnd.uniform(-1, 1)))
            if v.length > 1:
                continue
            c = p + v * clump
            out = (c - crown).normalized()
            nrm = (out * 0.6 + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * 0.7).normalized()
            ref = Vector((0, 1, 0)) if abs(nrm.y) < 0.9 else Vector((1, 0, 0))
            a = nrm.cross(ref).normalized()
            b = nrm.cross(a).normalized()
            s = card * rnd.uniform(0.75, 1.25) / 2
            rot = rnd.uniform(0, 2 * math.pi)
            a, b = a * math.cos(rot) + b * math.sin(rot), b * math.cos(rot) - a * math.sin(rot)
            q = [c - a * s - b * s, c + a * s - b * s, c + a * s + b * s, c - a * s + b * s]
            vs = [bm.verts.new(T(*pp)) for pp in q]
            f = bm.faces.new(vs)
            f.material_index = idx
            uvl.append(f)
    uvlay = bm.loops.layers.uv.new("UVMap")
    for f in uvl:
        for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            l[uvlay].uv = uv
    me = bpy.data.meshes.new(name + " Leaves")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["leafEver"] if ever else M["leaf"])
    ob = bpy.data.objects.new(name + " Leaves", me)
    C_TREES.objects.link(ob)
    return ob


make_tree("Front Oak", -3.6, 7.2, 5.2, 0.42, 2, 22, 5.2, 3, 2, 34, 0.25, 0.74, 300, 2.5, 0.95, seed=1)
make_tree("Porch Tree", 5.7, 3.3, 1.9, 0.16, 3, 40, 1.3, 1, 3, 45, 0.2, 0.8, 300, 1.35, 0.6, ever=True, seed=2)
for i, (x, z, s) in enumerate([(3.5, -23.5, 1.45), (-10.5, -22, 1.05), (-3, -28, 0.8), (13.2, -27.5, 1.3), (18.6, -25.5, 1.15)]):
    make_tree(f"Back Tree {i + 1}", x, z, 4.6 * s, 0.34 * s, 2, 24, 4.2 * s, 2, 2, 32, 0.28, 0.78, 260, 2.8 * s, 1.15 * s, seed=10 + i)
bgrnd = random.Random(5)
bg = []
for x in range(-64, 66, 7):
    bg.append((x + bgrnd.uniform(-2.5, 2.5), -36 + bgrnd.uniform(-2.5, 2.5)))
    bg.append((x + 4 + bgrnd.uniform(-2.5, 2.5), -45 + bgrnd.uniform(-3, 3)))
    bg.append((x + 2 + bgrnd.uniform(-2.5, 2.5), -55 + bgrnd.uniform(-3, 3)))
for z in range(-30, 44, 8):
    for x in (-44, -54, 50, 60):
        bg.append((x + bgrnd.uniform(-3, 3), z + bgrnd.uniform(-3, 3)))
for x in range(-56, 60, 10):
    if abs(x - 4) > 14:
        bg.append((x + bgrnd.uniform(-2.5, 2.5), 45 + bgrnd.uniform(-2, 2)))
    bg.append((x + 5 + bgrnd.uniform(-3, 3), 56 + bgrnd.uniform(-3, 3)))
for p in [(-30, -4), (-34, 10), (-28, 20), (28, 4), (30, 16), (-26, -20), (30, -22)]:
    bg.append(p)
for i, (x, z) in enumerate(bg):
    make_tree(f"Bg Tree {i + 1}", x, z, bgrnd.uniform(3.5, 5.5), bgrnd.uniform(0.3, 0.5), 2, 20, bgrnd.uniform(3.8, 5.2), 2, 2, 30,
              0.3, 0.78, 200, bgrnd.uniform(3.0, 3.8), 1.6, seed=100 + i)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "yellow_house_raw.blend"))
print("model built:", len(bpy.data.objects), "objects")
