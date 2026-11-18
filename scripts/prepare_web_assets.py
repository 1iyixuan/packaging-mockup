#!/usr/bin/env python3
"""Prepare web copies of embedded GLB color textures and a flat image. Requires Pillow."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import struct
import sys

from PIL import Image
from build_viewer import validate_glb


def prepare(model, out, dieline=None, texture_edge=2048, flat_edge=2400, quality=92):
    if texture_edge < 16 or flat_edge < 16 or not 1 <= quality <= 100:
        raise ValueError("Use positive image limits of at least 16 pixels, and quality 1..100")
    model = Path(model).resolve()
    validate_glb(model)
    output = Path(out).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be new or empty")
    flat = Path(dieline).resolve() if dieline else None
    if flat and not flat.is_file():
        raise ValueError("Flat image does not exist")
    raw = model.read_bytes()
    json_size = struct.unpack_from("<I", raw, 12)[0]
    doc = json.loads(raw[20:20 + json_size])
    binary_start = 28 + json_size
    if (len(raw) < binary_start or struct.unpack_from("<I", raw, binary_start - 4)[0] != 0x004E4942
            or binary_start + struct.unpack_from("<I", raw, binary_start - 8)[0] != len(raw)):
        raise ValueError("Expected one embedded BIN chunk")
    if (len(doc.get("buffers", [])) != 1 or doc["buffers"][0].get("uri")
            or any(view.get("buffer", 0) != 0 for view in doc.get("bufferViews", []))):
        raise ValueError("Use a GLB with one embedded buffer")
    binary = raw[binary_start:]
    color_images, data_images, alpha_images = set(), set(), set()
    for material in doc.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        texture_slots = [
            (pbr.get("baseColorTexture"), True, material.get("alphaMode", "OPAQUE") != "OPAQUE"),
            (material.get("emissiveTexture"), True, False),
            (pbr.get("metallicRoughnessTexture"), False, False),
            (material.get("normalTexture"), False, False),
            (material.get("occlusionTexture"), False, False),
        ]
        for extension in material.get("extensions", {}).values():
            if isinstance(extension, dict):
                texture_slots.extend((value, False, False) for key, value in extension.items()
                                     if key.endswith("Texture") and isinstance(value, dict))
        for texture, color, alpha in texture_slots:
            if texture is None:
                continue
            source = doc["textures"][texture["index"]].get("source")
            if source is not None:
                (color_images if color else data_images).add(source)
                if alpha:
                    alpha_images.add(source)

    replacements, images = {}, []
    for index in sorted(color_images - data_images):
        image = doc["images"][index]
        view_index = image.get("bufferView")
        if view_index is None:
            continue
        # Do not resize a buffer view shared with another image or accessor.
        if (sum(item.get("bufferView") == view_index for item in doc["images"]) != 1
                or any(item.get("bufferView") == view_index for item in doc.get("accessors", []))):
            continue
        view = doc["bufferViews"][view_index]
        offset = view.get("byteOffset", 0)
        with Image.open(BytesIO(binary[offset:offset + view["byteLength"]])) as opened:
            before = list(opened.size)
            texture = opened.convert("RGBA" if index in alpha_images else "RGB")
            texture.thumbnail((texture_edge, texture_edge), Image.Resampling.LANCZOS)
            packed = BytesIO()
            if index in alpha_images:
                texture.save(packed, "PNG", optimize=True)
                mime = "image/png"
            else:
                texture.save(packed, "JPEG", quality=quality, subsampling=0, optimize=True)
                mime = "image/jpeg"
            images.append(dict(index=index, before=before, after=list(texture.size),
                               bytes_before=view["byteLength"], bytes_after=len(packed.getvalue())))
            replacements[view_index] = packed.getvalue()
            image["mimeType"] = mime

    # Retain every geometry/data view byte-for-byte, while re-aligning view offsets.
    payload = bytearray()
    for index, view in enumerate(doc["bufferViews"]):
        start = view.get("byteOffset", 0)
        content = replacements.get(index)
        if content is None:
            content = binary[start:start + view["byteLength"]]
        payload.extend(b"\0" * (-len(payload) % 4))
        view["byteOffset"] = len(payload)
        view["byteLength"] = len(content)
        payload.extend(content)
    payload.extend(b"\0" * (-len(payload) % 4))
    doc["buffers"][0]["byteLength"] = len(payload)
    metadata = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    metadata += b" " * (-len(metadata) % 4)
    result = (struct.pack("<4sII", b"glTF", 2, len(metadata) + len(payload) + 28)
              + struct.pack("<II", len(metadata), 0x4E4F534A) + metadata
              + struct.pack("<II", len(payload), 0x004E4942) + payload)
    output.mkdir(parents=True, exist_ok=True)
    target = output / "model.glb"
    target.write_bytes(result)
    validate_glb(target)
    report = dict(model_bytes_before=len(raw), model_bytes_after=len(result),
                  color_images=images, original=str(model.name))
    if flat:
        with Image.open(flat) as opened:
            before = list(opened.size)
            opened.thumbnail((flat_edge, flat_edge), Image.Resampling.LANCZOS)
            preview = output / "dieline.webp"
            opened.save(preview, "WEBP", quality=quality, method=6, exact=True)
            report["flat"] = dict(before=before, after=list(opened.size),
                                  bytes_before=flat.stat().st_size, bytes_after=preview.stat().st_size)
    (output / "web-assets.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dieline")
    parser.add_argument("--texture-edge", type=int, default=2048)
    parser.add_argument("--flat-edge", type=int, default=2400)
    parser.add_argument("--quality", type=int, default=92)
    try:
        print(json.dumps(prepare(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Preparation failed: {error}\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

