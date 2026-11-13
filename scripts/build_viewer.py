#!/usr/bin/env python3
"""Build a self-contained static packaging viewer. Never uploads or deploys."""
import argparse
import hashlib
import html
import json
import math
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


VIEWER_FILES = (
    "index.html", "viewer.css", "viewer.js", "fold.js",
    "vendor/model-viewer.min.js", "vendor/LICENSE", "vendor/provenance.json",
    "vendor/square.svg", "vendor/box.svg", "vendor/expand.svg", "vendor/shrink.svg",
    "vendor/lucide-LICENSE",
)
DEFAULT_ORBIT = "-26deg 77deg 75%"
ORBIT_FORMAT = r"(-?\d+(?:\.\d+)?)deg\s+(\d+(?:\.\d+)?)deg\s+(\d+(?:\.\d+)?)%"
OUTLINE_POINT = r"\d+(?:\.\d+)?%\s+\d+(?:\.\d+)?%"


def preview_image(path, label):
    if path is None:
        return None
    image = Path(path).resolve()
    if not image.is_file() or image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"{label} must be an existing PNG, JPEG or WebP image")
    return image


def coordinates(values, size):
    return (isinstance(values, list) and len(values) == size
            and all(type(value) in (int, float) and math.isfinite(value) for value in values))


def read_fold(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Fold configuration must be an object")
    artwork = config.get("artwork")
    if not coordinates(artwork, 2) or min(artwork) <= 0:
        raise ValueError("Fold artwork must specify positive width and height")
    panels = config.get("panels")
    if not isinstance(panels, list) or len(panels) < 2:
        raise ValueError("Fold configuration requires a front panel and at least one hinged panel")
    for index, panel in enumerate(panels):
        label = f"Fold panel {index}"
        if not isinstance(panel, dict) or not coordinates(panel.get("bounds"), 4):
            raise ValueError(f"{label} must have four bounds coordinates")
        left, top, right, bottom = panel["bounds"]
        if not (0 <= left < right <= artwork[0] and 0 <= top < bottom <= artwork[1]):
            raise ValueError(f"{label} bounds must be inside the artwork")
        outline = panel.get("outline")
        if outline is not None and (not isinstance(outline, str) or not re.fullmatch(
                rf"{OUTLINE_POINT}(?:\s*,\s*{OUTLINE_POINT}){{2,}}", outline)):
            raise ValueError(f"{label} outline must list at least three percentage coordinate pairs")
        if index == 0:
            if any(key in panel for key in ("parent", "hinge", "axis", "angle", "timing")):
                raise ValueError(f"{label} is the front panel and must remain fixed")
            continue
        parent = panel.get("parent")
        if type(parent) is not int or not 0 <= parent < index:
            raise ValueError(f"{label} must point to an earlier parent panel")
        hinge, axis, angle = panel.get("hinge"), panel.get("axis"), panel.get("angle")
        if (axis not in ("X", "Y") or not coordinates(hinge, 2)
                or type(angle) not in (int, float) or not -180 <= angle <= 180):
            raise ValueError(f"{label} requires a hinge, axis X/Y and an angle from -180 to 180")
        x, y = hinge
        if not (left <= x <= right and top <= y <= bottom
                and (y in (top, bottom) if axis == "X" else x in (left, right))):
            raise ValueError(f"{label} hinge must be on the folding edge")
        timing = panel.get("timing", [0, 1])
        if not coordinates(timing, 2) or not 0 <= timing[0] < timing[1] <= 1:
            raise ValueError(f"{label} timing must satisfy 0 <= start < end <= 1")
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def build(model, title, out, subtitle="", poster=None, orbit=DEFAULT_ORBIT,
          dieline=None, fold_config=None, mobile_orbit=None):
    model, out = Path(model).resolve(), Path(out).resolve()
    if not title.strip():
        raise ValueError("Title must not be empty")
    match = re.fullmatch(ORBIT_FORMAT, orbit)
    if not match or mobile_orbit is not None and not re.fullmatch(ORBIT_FORMAT, mobile_orbit):
        raise ValueError("Orbit format: '-26deg 77deg 75%'")
    if mobile_orbit is None:
        theta, phi, radius = match.groups()
        mobile_orbit = f"{theta}deg {phi}deg {max(128, float(radius)):g}%"
    poster = preview_image(poster, "Poster")
    dieline = preview_image(dieline, "Dieline")
    if fold_config and not dieline:
        raise ValueError("A fold configuration requires a dieline image")
    fold = read_fold(fold_config) if fold_config else None
    metadata = validate_glb(model)
    template = Path(__file__).resolve().parents[1] / "assets" / "viewer"
    for name in VIEWER_FILES:
        if not (template / name).is_file():
            raise ValueError("Missing bundled viewer asset: " + name)
    archive = out.with_name(out.name + ".zip")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Output directory must be new or empty; use a new version directory")
    if archive.exists():
        raise ValueError("Output ZIP already exists; use a new version directory")
    revision = hashlib.sha256()
    for source in (metadata["sha256"], title, subtitle, orbit, mobile_orbit, fold or ""):
        revision.update(source.encode("utf-8") + b"\0")
    for asset in [*(template / name for name in VIEWER_FILES), poster, dieline]:
        if asset:
            revision.update(hashlib.sha256(asset.read_bytes()).digest())
    version = revision.hexdigest()[:12]
    out.mkdir(parents=True, exist_ok=True)
    (out / "vendor").mkdir()
    for name in VIEWER_FILES[1:]:
        shutil.copy2(template / name, out / name)
    shutil.copy2(model, out / "model.glb")
    images = {}
    for name, source in (("poster", poster), ("dieline", dieline)):
        if source:
            filename = name + source.suffix.lower()
            shutil.copy2(source, out / filename)
            images[name] = f"./{filename}?v={version}"
    if fold:
        (out / "fold.json").write_text(fold, encoding="utf-8")
    title, subtitle = title.strip(), subtitle.strip()
    combined = " · ".join(filter(None, (title, subtitle)))
    heading = "<span>" + html.escape(title) + "</span>"
    if subtitle:
        heading += "<span>" + html.escape(subtitle) + "</span>"
    page = Template((template / "index.html").read_text(encoding="utf-8")).substitute(
        page_title=html.escape(combined), description=html.escape(combined), heading=heading,
        revision=version, orbit=orbit, mobile_orbit=mobile_orbit,
        poster_attr=f'poster="{images["poster"]}"' if poster else "",
        dieline_src=f'src="{images["dieline"]}"' if dieline else "",
        mode_attr="" if dieline else "hidden",
        fold_attr=f'data-fold-config="./fold.json?v={version}"' if fold else "",
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    manifest = {"title": title, "subtitle": subtitle, "model": metadata, "initialOrbit": orbit,
                "mobileOrbit": mobile_orbit, "flatView": bool(dieline), "foldAnimation": bool(fold),
                "revision": version}
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
    parser.add_argument("--dieline", help="PNG, JPEG or WebP shown in flat view")
    parser.add_argument("--fold-config", help="JSON describing the project-specific panels and hinges")
    parser.add_argument("--orbit", default=DEFAULT_ORBIT)
    parser.add_argument("--mobile-orbit")
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
