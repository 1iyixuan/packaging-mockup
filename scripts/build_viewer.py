#!/usr/bin/env python3
"""Build a self-contained static packaging viewer. Never uploads or deploys."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import struct
from string import Template
import sys
import zipfile


def validate_glb(path):
    data = Path(path).read_bytes()
    if len(data) < 20:
        raise ValueError("GLB is too short")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ValueError("Expected a complete glTF 2.0 binary file")
    position, document = 12, None
    while position < len(data):
        if position + 8 > len(data):
            raise ValueError("Truncated GLB chunk header")
        size, kind = struct.unpack_from("<II", data, position)
        position += 8
        if size % 4 or position + size > len(data):
            raise ValueError("Invalid GLB chunk length")
        if document is None:
            if kind != 0x4E4F534A:
                raise ValueError("GLB first chunk must contain JSON")
            document = json.loads(data[position:position + size].decode("utf-8"))
        position += size
    if not isinstance(document, dict) or document.get("asset", {}).get("version") != "2.0":
        raise ValueError("Missing glTF 2.0 asset metadata")
    if not document.get("meshes"):
        raise ValueError("GLB has no product meshes")
    for resource in document.get("buffers", []) + document.get("images", []):
        uri = resource.get("uri", "")
        if uri and not uri.startswith("data:"):
            raise ValueError("GLB contains external resources; embed textures and buffers first")
    compressed = {"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"}
    if compressed.intersection(document.get("extensionsUsed", [])):
        raise ValueError("Export an uncompressed GLB to avoid external decoder dependencies")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "meshes": len(document["meshes"])}


def build(model, title, out, subtitle="", poster=None, orbit="35deg 75deg 135%"):
    model, out = Path(model).resolve(), Path(out).resolve()
    if not title.strip():
        raise ValueError("Title must not be empty")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?deg\s+\d+(?:\.\d+)?deg\s+\d+(?:\.\d+)?%", orbit):
        raise ValueError("Orbit format: '35deg 75deg 105%'")
    metadata = validate_glb(model)
    template = Path(__file__).resolve().parents[1] / "assets" / "viewer"
    required = ("index.html", "viewer.css", "viewer.js", "vendor/model-viewer.min.js", "vendor/LICENSE", "vendor/provenance.json")
    for name in required:
        if not (template / name).is_file():
            raise ValueError("Missing bundled viewer asset: " + name)
    archive = out.with_name(out.name + ".zip")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output directory must be new or empty; use a new version directory")
    if archive.exists():
        raise ValueError("Output ZIP already exists; use a new version directory")
    poster_name = None
    if poster:
        poster = Path(poster).resolve()
        if not poster.is_file() or poster.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Poster must be an existing PNG, JPEG or WebP image")
        poster_name = "poster" + poster.suffix.lower()
    out.mkdir(parents=True, exist_ok=True)
    (out / "vendor").mkdir()
    for name in required[1:]:
        shutil.copy2(template / name, out / name)
    shutil.copy2(model, out / "model.glb")
    if poster:
        shutil.copy2(poster, out / poster_name)
    title, subtitle = title.strip(), subtitle.strip()
    combined = " · ".join(filter(None, (title, subtitle)))
    heading = "<span>" + html.escape(title) + "</span>"
    if subtitle:
        heading += "<span>" + html.escape(subtitle) + "</span>"
    page = Template((template / "index.html").read_text(encoding="utf-8")).substitute(
        page_title=html.escape(combined), description=html.escape(combined), heading=heading,
        poster_attr=f'poster="./{poster_name}"' if poster_name else "", orbit=html.escape(orbit, quote=True),
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    manifest = {"title": title, "subtitle": subtitle, "model": metadata, "initialOrbit": orbit}
    (out / "asset-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(out.rglob("*")):
            if file.is_file():
                bundle.write(file, file.relative_to(out).as_posix())
    return {"directory": str(out), "archive": str(archive), "model": metadata}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--poster")
    parser.add_argument("--orbit", default="35deg 75deg 135%")
    args = parser.parse_args()
    try:
        result = build(**vars(args))
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
