"""Export the house and yard (no render-only trees/grass) to GLB in the web app's coordinates.

python3 export.py out.glb
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "yellow_house_raw.blend"))
keep = set(bpy.data.collections["House"].objects) | set(bpy.data.collections["Yard"].objects)
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    ob.select_set(ob in keep)
bpy.context.view_layer.objects.active = next(iter(keep))
bpy.ops.export_scene.gltf(
    filepath=out,
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_yup=True,
    export_image_format="JPEG",
    export_jpeg_quality=82,
    export_materials="EXPORT",
    export_texcoords=True,
    export_normals=True,
    export_tangents=False,
    export_cameras=False,
    export_lights=False,
)
print("exported", out, os.path.getsize(out) // 1024, "KB")
