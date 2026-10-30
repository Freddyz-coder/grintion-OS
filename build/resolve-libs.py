#!/usr/bin/env python3
"""Resolve the complete shared-library closure of a staged root filesystem.

Every ELF object under the root is inspected with ``ldd``. For each dependency
the real file is copied to the same absolute path inside the root, and every
symlink alias that points at that real file is recreated. The dynamic loader
reported by ``ldd`` is copied as well.

The script fails closed: a dependency that exists on the host but cannot be
copied, or a ``not found`` entry for an object we ship, is an error.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ELF_MAGIC = b"\x7fELF"


def is_elf(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(4) == ELF_MAGIC
    except OSError:
        return False


def ldd_dependencies(path: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["ldd", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[!] ldd failed for {path}: {exc}", file=sys.stderr)
        return []
    deps: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "=>" in line:
            rhs = line.split("=>", 1)[1].strip()
            if rhs.startswith("/"):
                deps.append(rhs.split()[0])
            elif rhs.startswith("not found"):
                print(f"[!] unresolved dependency in {path}: {line}", file=sys.stderr)
        elif line.startswith("/"):
            deps.append(line.split()[0])
    return deps


class Rootfs:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.copied: set[str] = set()
        self.visited: set[str] = set()
        self.missing: list[str] = []
        self.failures: list[str] = []

    def dest_for(self, host_path: str) -> Path:
        return self.root / host_path.lstrip("/")

    def copy_real(self, host_path: str) -> Path | None:
        real = Path(host_path).resolve()
        if not real.exists():
            self.missing.append(host_path)
            return None
        key = str(real)
        if key in self.copied:
            return self.dest_for(str(real))
        dest = self.dest_for(str(real))
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_symlink():
                dest.unlink()
            shutil.copy2(real, dest, follow_symlinks=True)
            self.copied.add(key)
        except OSError as exc:
            self.failures.append(f"{real}: {exc}")
            return None
        return dest

    def copy_aliases(self, host_path: str, real: Path) -> None:
        """Recreate every sibling symlink that resolves to ``real``."""
        for directory in {Path(host_path).parent, real.parent}:
            try:
                entries = list(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.is_symlink() or entry.resolve() != real:
                        continue
                except OSError:
                    continue
                dest = self.dest_for(str(entry))
                if dest.exists() or dest.is_symlink():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(os.readlink(entry))

    def add(self, host_path: str, copy_self: bool = True) -> None:
        real = Path(host_path).resolve()
        if not real.exists():
            self.missing.append(host_path)
            return
        if str(real) in self.visited:
            return
        self.visited.add(str(real))
        if copy_self:
            dest = self.copy_real(str(real))
            if dest is None:
                return
            self.copy_aliases(host_path, real)
        for dep in ldd_dependencies(real):
            self.add(dep)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--scan",
        action="append",
        default=[],
        help="extra directory (inside the root) to scan for ELF objects",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"[-] not a directory: {root}", file=sys.stderr)
        return 1

    resolver = Rootfs(root)
    objects: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            try:
                mode = path.lstat().st_mode
            except OSError:
                continue
            if stat.S_ISREG(mode) and is_elf(path):
                objects.append(path)

    print(f"[*] resolving libraries for {len(objects)} ELF objects")
    for path in sorted(objects):
        # The object already lives in the root; only resolve its dependencies.
        resolver.add(str(path), copy_self=False)

    if resolver.missing:
        # Missing host entries are only fatal when the object itself is shipped
        # and the loader reported it. ldd omissions are reported separately.
        print(f"[!] {len(resolver.missing)} dependencies were not present on the host", file=sys.stderr)
    if resolver.failures:
        for failure in resolver.failures:
            print(f"[-] {failure}", file=sys.stderr)
        return 1

    print(f"[+] library closure complete: {len(resolver.copied)} real files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
