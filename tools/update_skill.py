"""Install the latest published packaging-mockup release into one skill directory."""

import argparse
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


NAME = "packaging-mockup"
REPOSITORY = f"1iyixuan/{NAME}"
LATEST = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MANIFEST = ".release-files.json"


def download(url):
    request = Request(url, headers={"User-Agent": "packaging-mockup-updater"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def version_tuple(version):
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError(f"Unexpected release version: {version!r}")
    return tuple(map(int, version.split(".")))


def inventory(directory):
    return {
        path.relative_to(directory).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != directory / MANIFEST
    }


def unpack(package, destination, version):
    members = set()
    with ZipFile(BytesIO(package)) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if member.is_dir() and member.filename == f"{NAME}/":
                continue
            if (
                len(parts) < 2
                or parts[0] != NAME
                or any(part in {".", ".."} for part in parts)
                or "\\" in member.filename
                or ":" in member.filename
                or member.filename.casefold() in members
            ):
                raise ValueError(f"Unexpected ZIP entry: {member.filename}")
            members.add(member.filename.casefold())
            archive.extract(member, destination)

    skill = destination / NAME
    if (
        (skill / "VERSION").read_text(encoding="utf-8").strip() != version
        or "\nname: packaging-mockup\n" not in (skill / "SKILL.md").read_text(encoding="utf-8")
        or not (skill / "agents" / "openai.yaml").is_file()
    ):
        raise ValueError("Release contents do not match the skill and version")
    return skill


def update(target, adopt_existing=False):
    try:
        tag = json.loads(download(LATEST))["tag_name"]
    except HTTPError as error:
        if error.code != 404:
            raise
        print("No published release is available.")
        return
    if not tag.startswith("v"):
        raise ValueError(f"Unexpected release tag: {tag!r}")
    version = tag[1:]
    candidate_version = version_tuple(version)
    manifest_path = target / MANIFEST
    baseline = None

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if candidate_version <= version_tuple(manifest["version"]):
            print(f"Installed v{manifest['version']} is current.")
            return
        baseline = manifest["files"]
    elif target.exists() and not adopt_existing:
        raise ValueError("Existing installation is unmanaged. Review it and run once with --adopt-existing.")

    filename = f"{NAME}-{tag}.zip"
    release = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    checksum = download(f"{release}/SHA256SUMS").decode("ascii").split()
    package = download(f"{release}/{filename}")
    if checksum != [sha256(package).hexdigest(), filename]:
        raise ValueError("Package SHA-256 verification failed")

    backups = target.parent.parent / "skill-backups"
    backups.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{NAME}-", dir=backups) as temporary:
        staged = unpack(package, Path(temporary), version)
        state = {"version": version, "files": inventory(staged)}
        (staged / MANIFEST).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        if baseline is not None and inventory(target) != baseline:
            raise ValueError("Local skill files have changed. Keep them and reconcile before updating.")

        backup = None
        if target.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = backups / f"{NAME}-before-{tag}-{timestamp}"
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None and not target.exists():
                backup.rename(target)
            raise

    print(f"Installed {tag} at {target}")
    if backup:
        print(f"Previous installation: {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--adopt-existing", action="store_true", help="Back up and enroll an existing unmanaged copy")
    args = parser.parse_args()
    target = args.skill_dir.expanduser().absolute()
    if (
        target.name != NAME
        or not target.parent.is_dir()
        or target.resolve() != target.parent.resolve() / NAME
        or (target.exists() and not target.is_dir())
    ):
        parser.error("--skill-dir must name packaging-mockup inside the actual personal skill directory")
    target = target.resolve()
    try:
        update(target, args.adopt_existing)
    except (OSError, ValueError, KeyError, BadZipFile) as error:
        parser.exit(1, f"Update stopped: {error}\n")


if __name__ == "__main__":
    main()
