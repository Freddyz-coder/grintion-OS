#!/usr/bin/env python3
"""Seed pacman's local database with packages already present in the image.

The Grintion live rootfs is assembled from host files rather than installed by
pacman. Without DB entries, `pacman -S tree` would try to install glibc and
every other dependency over the existing files and fail on conflicts. This
script records the packages whose commands are actually shipped, plus their
dependency closure, so pacman installs only the new package.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

# Packages that make the pacman backend itself work. They are copied even if no
# command in the required list maps to them.
BACKEND_PACKAGES = {
    "acl", "archlinux-keyring", "bash", "brotli", "bzip2", "curl", "gpgme",
    "gnupg", "krb5", "libarchive", "libidn2", "libpsl", "libseccomp",
    "libssh2", "libxml2", "lz4", "nghttp2", "nghttp3", "ngtcp2", "openssl",
    "pacman", "sqlite", "xz", "zlib", "zstd",
}


def sections(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("%") and line.endswith("%"):
            current = line.strip("%")
            result[current] = []
        elif current is not None and line:
            result[current].append(line)
    return result


def package_names(local_db: Path) -> dict[str, Path]:
    entries: dict[str, Path] = {}
    for entry in local_db.iterdir():
        desc = entry / "desc"
        if not entry.is_dir() or not desc.is_file():
            continue
        name = sections(desc).get("NAME", [""])[0]
        if name:
            entries[name] = entry
    return entries


def recorded_files(entry: Path) -> list[str]:
    files = entry / "files"
    if not files.is_file():
        return []
    return [path for path in sections(files).get("FILES", [])
            if path and not path.endswith("/")]


def declared_binaries(entry: Path) -> list[str]:
    return [path for path in recorded_files(entry)
            if path.startswith(("usr/bin/", "usr/sbin/", "bin/", "sbin/"))]


def declared_libraries(entry: Path) -> list[str]:
    return [path for path in recorded_files(entry)
            if path.startswith(("usr/lib/", "lib/"))
            and ".so" in path.rsplit("/", 1)[-1]]


def installed_packages(selected: dict[str, Path], root: Path) -> tuple[dict[str, Path], list[str]]:
    """Drop DB entries for packages whose files are absent from the rootfs.

    pacman trusts a local DB entry: a seeded package is treated as installed and
    is never reinstalled as a dependency, even when its files were never copied.
    A package is kept when ANY of these conditions hold:
      1. It ships at least one binary that exists in the rootfs.
      2. It ships only shared libraries and ALL declared .so files exist.
      3. It is a data package (no binaries, no libraries) and at least one
         declared file exists.

    Rationale for rule 1: resolve-libs.py copies all required shared-library
    dependencies after this filter runs; we do not punish a binary package for
    having a companion .so that hasn't been copied yet.  Only packages whose
    primary artefact (a binary) is completely absent should be dropped.
    """
    installed: dict[str, Path] = {}
    dropped: list[str] = []
    for name, entry in selected.items():
        binaries = declared_binaries(entry)
        libraries = declared_libraries(entry)
        files = recorded_files(entry)

        if binaries:
            # Keep if at least one declared binary is present; resolve-libs.py
            # will satisfy any shared-library deps afterwards.
            if any((root / path).is_file() for path in binaries):
                installed[name] = entry
            else:
                dropped.append(name)
        elif libraries:
            # Library-only package: all declared .so files must be present.
            if all((root / path).is_file() or (root / path).is_symlink() for path in libraries):
                installed[name] = entry
            else:
                dropped.append(name)
        else:
            # Data package: at least one declared file must exist.
            if any((root / path).is_file() or (root / path).is_symlink() for path in files):
                installed[name] = entry
            else:
                dropped.append(name)
    return installed, sorted(dropped)


def commands_from_config(repo: Path) -> list[str]:
    commands: list[str] = []
    for name in ("rootfs.required-binaries", "rootfs.optional-binaries"):
        for line in (repo / "config" / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--local-db", type=Path, default=Path("/var/lib/pacman/local"))
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    entries = package_names(args.local_db)
    wanted: set[str] = set(BACKEND_PACKAGES)

    for command in commands_from_config(repo):
        path = shutil.which(command)
        if not path:
            continue
        result = subprocess.run(
            ["pacman", "-Qoq", path], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            wanted.update(line.strip() for line in result.stdout.splitlines() if line.strip())

    selected: dict[str, Path] = {}
    missing: set[str] = set()
    queue = list(wanted)
    while queue:
        name = queue.pop()
        if name in selected:
            continue
        entry = entries.get(name)
        if entry is None:
            missing.add(name)
            continue
        selected[name] = entry
        for dependency in sections(entry / "desc").get("DEPENDS", []):
            dependency = re.split(r"[<>=]", dependency, maxsplit=1)[0].strip()
            if dependency:
                queue.append(dependency)

    selected, dropped = installed_packages(selected, args.root)

    destination = args.root / "var/lib/pacman/local"
    destination.mkdir(parents=True, exist_ok=True)
    for entry in selected.values():
        target = destination / entry.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(entry, target)

    db_version = args.local_db / "ALPM_DB_VERSION"
    if db_version.is_file():
        shutil.copy2(db_version, destination / "ALPM_DB_VERSION")

    print(f"[+] pacman DB seeded with {len(selected)} packages"
          f" ({len(missing)} dependencies not installed on the host,"
          f" {len(dropped)} not present in the rootfs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
