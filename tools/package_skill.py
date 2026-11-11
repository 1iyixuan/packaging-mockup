"""Build a versioned, reproducible install package and its SHA-256 checksum."""

import argparse
from hashlib import sha256
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise SystemExit("VERSION must be a numeric major.minor.patch version")

    paths = [ROOT / "SKILL.md", ROOT / "VERSION"]
    for directory in ("agents", "assets", "references", "scripts"):
        paths.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and path.suffix not in {".pyc", ".pyo"}
            and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
        )
    if ROOT / "agents" / "openai.yaml" not in paths:
        raise SystemExit("Missing agents/openai.yaml")

    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f"packaging-mockup-v{version}.zip"
    with ZipFile(archive, "w") as package:
        for path in sorted(paths):
            member = ZipInfo(f"packaging-mockup/{path.relative_to(ROOT).as_posix()}")
            package.writestr(member, path.read_bytes(), compress_type=ZIP_DEFLATED)

    checksum = sha256(archive.read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(
        f"{checksum}  {archive.name}\n", encoding="ascii", newline="\n"
    )
    print(archive)


if __name__ == "__main__":
    main()
