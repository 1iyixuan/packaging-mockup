"""Run in Blender: --python export_glb.py -- --collection NAME --output PATH."""
import argparse
from pathlib import Path
import sys

import bpy


def export_product(collection_name, output):
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        raise ValueError("Product collection not found: " + collection_name)
    output = Path(output).resolve()
    if output.suffix.lower() != ".glb":
        raise ValueError("Output must use .glb extension")
    if output.exists():
        raise ValueError("Output already exists; choose a new version path")
    if bpy.context.mode != "OBJECT":
        raise ValueError("Switch to Object mode before exporting")
    members = [obj for obj in collection.all_objects if obj.type in {"MESH", "EMPTY", "ARMATURE"}]
    meshes = [obj for obj in members if obj.type == "MESH"]
    if not meshes:
        raise ValueError("Product collection contains no mesh objects")
    layer_objects = {obj.name for obj in bpy.context.view_layer.objects}
    for obj in members:
        if obj.name not in layer_objects or obj.hide_get() or obj.hide_select or not obj.visible_get():
            raise ValueError("Product member is hidden, excluded or not selectable: " + obj.name)
    for obj in collection.all_objects:
        if obj.type not in {"MESH", "EMPTY", "ARMATURE", "LIGHT", "CAMERA"}:
            raise ValueError("Convert unsupported product object to mesh first: " + obj.name)
    before = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in members:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        options = {
            "filepath": str(output), "export_format": "GLB", "use_selection": True,
            "export_cameras": False, "export_lights": False, "export_animations": False,
            "export_apply": True,
        }
        supported = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
        missing = set(options).difference(supported)
        if missing:
            raise RuntimeError("Unsupported glTF exporter options: " + ", ".join(sorted(missing)))
        result = bpy.ops.export_scene.gltf(**options)
        if "FINISHED" not in result or not output.is_file() or output.stat().st_size < 20:
            raise RuntimeError("glTF exporter did not produce a complete file")
        print("PACKAGING_GLB_EXPORTED", str(output), output.stat().st_size, flush=True)
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in before:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = active


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--output", required=True)
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(tail)
    export_product(args.collection, args.output)


if __name__ == "__main__":
    main()
