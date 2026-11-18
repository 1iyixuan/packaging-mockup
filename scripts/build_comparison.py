#!/usr/bin/env python3
"""Build a local multi-scheme packaging comparison from confirmed project assets."""
import argparse
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path
import shutil
from string import Template
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from build_viewer import preview_image, read_fold, validate_glb


def build(config, out):
    config_path = Path(config).resolve()
    configuration = json.loads(config_path.read_text(encoding="utf-8-sig"))
    title = configuration.get("title", "")
    subtitle = configuration.get("subtitle", "包装展示")
    if not isinstance(title, str) or not title.strip() or not isinstance(subtitle, str):
        raise ValueError("Specify a title and a string subtitle")
    dimensions = configuration.get("dimensions_mm")
    if (not isinstance(dimensions, list) or len(dimensions) != 3
            or not all(type(n) in (int, float) and math.isfinite(n) and n > 0 for n in dimensions)):
        raise ValueError("dimensions_mm must contain positive width, depth and height in millimeters")
    schemes = configuration.get("schemes")
    if not isinstance(schemes, list) or len(schemes) < 2:
        raise ValueError("Use two or more schemes, or build_viewer.py for a single scheme")

    assets = []
    identities = set()
    for item in schemes:
        if not isinstance(item, dict):
            raise ValueError("Each scheme must be an object")
        identity, name = item.get("id"), item.get("name")
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise ValueError("Each scheme needs a unique nonempty string id")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Each scheme needs a display name")
        identities.add(identity)
        model = (config_path.parent / item["model"]).resolve()
        image = preview_image(config_path.parent / item["dieline"], "Dieline")
        if image is None:
            raise ValueError("Provide the scheme's confirmed flat image")
        fold = read_fold(config_path.parent / item["fold_config"]) if item.get("fold_config") else None
        assets.append(dict(id=identity, name=name.strip(), model=model, image=image,
                           fold=fold, metadata=validate_glb(model)))

    output = Path(out).resolve()
    archive = output.with_name(output.name + ".zip")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    if archive.exists():
        raise ValueError("Output ZIP already exists, use a new version path")
    skill = Path(__file__).resolve().parents[1]
    template = skill / "assets" / "comparison"
    vendor = skill / "assets" / "viewer" / "vendor"
    runtime_files = ("index.html", "viewer.css", "viewer.js", "fold.js")
    for name in runtime_files:
        if not (template / name).is_file():
            raise ValueError("Missing comparison template " + name)
    if not vendor.is_dir():
        raise ValueError("Missing local viewer library")
    revision = sha256(json.dumps(dict(title=title, subtitle=subtitle, dimensions=dimensions),
                                 ensure_ascii=False).encode())
    for file in [*(template / name for name in runtime_files),
                 *sorted(file for file in vendor.rglob("*") if file.is_file())]:
        revision.update(sha256(file.read_bytes()).digest())
    for item in assets:
        revision.update(json.dumps(dict(id=item["id"], name=item["name"], fold=item["fold"]),
                                   ensure_ascii=False).encode())
        revision.update(item["metadata"]["sha256"].encode())
        revision.update(sha256(item["image"].read_bytes()).digest())
    version = revision.hexdigest()[:12]

    output.mkdir(parents=True, exist_ok=True)
    for name in runtime_files[1:]:
        shutil.copy2(template / name, output / name)
    shutil.copytree(vendor, output / "vendor")
    runtime, model_files = [], []
    for i, item in enumerate(assets, 1):
        model_name = f"model-{i}.glb"
        image_name = f"dieline-{i}{item['image'].suffix.lower()}"
        fold_name = f"fold-{i}.json" if item["fold"] else None
        shutil.copy2(item["model"], output / model_name)
        shutil.copy2(item["image"], output / image_name)
        if fold_name:
            (output / fold_name).write_text(item["fold"], encoding="utf-8")
        runtime.append(dict(id=item["id"], name=item["name"],
                            model=f"./{model_name}?v={version}",
                            dieline=f"./{image_name}?v={version}", fold_config=fold_name))
        model_files.append(dict(id=item["id"], name=item["name"], file=model_name, **item["metadata"]))

    half_height = dimensions[2] / 2000
    spacing = dimensions[0] / 1000 * 1.65
    extra_models, buttons, details, images = [], [], [], []
    for i, item in enumerate(runtime):
        offset = (i - (len(runtime) - 1) / 2) * spacing
        name, source = escape(item["name"], quote=True), escape(item["model"], quote=True)
        extra_models.append(
            f'<extra-model src="{source}" offset="{offset}m {-half_height}m 0m"></extra-model>')
        buttons.append(f'<button type="button" data-model="{i}">查看{name}</button>')
        details.append(f"""<model-viewer data-src="{source}" alt="{name}，{escape(title)}包装"
            interaction-prompt="none" loading="eager" reveal="auto"
            camera-orbit="16deg 80deg 108%" field-of-view="30deg"
            min-camera-orbit="auto 2deg auto" max-camera-orbit="auto 178deg auto"
            min-field-of-view="17deg" max-field-of-view="45deg"
            environment-image="neutral" tone-mapping="neutral" exposure="1"
            shadow-intensity="0" tabindex="0"></model-viewer>""")
        images.append(f'<img data-src="{escape(item["dieline"], quote=True)}" alt="{name}展开图" draggable="false">')

    heading = f'<h1><span>{escape(title.strip())}</span><span id="compare-title">{escape(subtitle)}</span></h1>'
    settings = json.dumps(dict(dimensions_mm=dimensions, schemes=runtime), ensure_ascii=False)
    html = Template((template / "index.html").read_text(encoding="utf-8")).substitute(
        revision=version, comparison=escape(settings, quote=True),
        page_title=escape(" · ".join(filter(None, (title.strip(), subtitle)))),
        heading=heading, scheme_count=len(runtime), extra_models="\n".join(extra_models),
        scheme_buttons="\n".join(buttons), detail_models="\n".join(details),
        artwork_images="\n".join(images),
        fold_surfaces='<div class="fold-surface"></div>' * len(runtime))
    (output / "index.html").write_text(html, encoding="utf-8")
    manifest = dict(title=title.strip(), subtitle=subtitle, models=model_files,
                    dimensions_mm=dimensions, revision=version,
                    flatView=True, foldAnimation=any(item["fold"] for item in assets),
                    mobileFoldAnimation=False)
    (output / "asset-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as bundle:
        for file in sorted(output.rglob("*")):
            if file.is_file():
                bundle.write(file, file.relative_to(output).as_posix())
    return dict(directory=str(output), archive=str(archive), revision=version, models=model_files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = build(**vars(args))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

