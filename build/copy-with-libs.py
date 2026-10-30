#!/usr/bin/env python3
"""Copy binaries and their complete dynamic-library closure into a rootfs.

Usage:
    copy-with-libs.py --root ROOTFS --dest usr/bin BINARY [BINARY...]
    copy-with-libs.py --root ROOTFS --dest usr/lib --lib LIB [LIB...]

The resolver follows ldd recursively, preserves the original directory layout
under the rootfs, and recreates symlink aliases so the dynamic loader can find
SONAMEs such as libfoo.so.1 as well as the real libfoo.so.1.2.3.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

seen_files: set[str] = set()
seen_libs: set[str] = set()


def run_ldd(path: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["ldd", path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    deps: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "=>" in line:
            rhs = line.split("=>", 1)[1].strip()
            if rhs.startswith("/"):
                deps.append(rhs.split()[0])
        elif line.startswith("/"):
            deps.append(line.split()[0])
    return deps


def ensure_parent(root: Path, dest: Path) -> None:
    rel = dest.relative_to(root)
    parent = root
    for part in rel.parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            parent.unlink()
        parent.mkdir(exist_ok=True)


def copy_real(root: Path, real: str) -> None:
    real_path = Path(real).resolve()
    if not real_path.exists():
        return
    rel = real_path.relative_to("/")
    dest = root / rel
    ensure_parent(root, dest)
    if str(real_path) in seen_files:
        return
    if dest.exists() and not dest.is_symlink():
        seen_files.add(str(real_path))
        return
    if dest.is_symlink():
        dest.unlink()
    shutil.copy2(real_path, dest, follow_symlinks=True)
    seen_files.add(str(real_path))


def copy_aliases(root: Path, requested: str, real: str) -> None:
    """Recreate the requested path and every sibling symlink to the same real file."""
    real_path = Path(real).resolve()
    requested_path = Path(requested)
    directories = {requested_path.parent, real_path.parent}
    for directory in directories:
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            try:
                if not entry.is_symlink():
                    continue
                if entry.resolve() != real_path:
                    continue
            except OSError:
                continue
            rel = entry.relative_to("/")
            dest = root / rel
            ensure_parent(root, dest)
            if dest.exists() or dest.is_symlink():
                continue
            dest.symlink_to(os.readlink(entry))


def copy_one(root: Path, requested: str) -> None:
    requested_path = Path(requested)
    if not requested_path.exists():
        print(f"[-] missing: {requested}", file=sys.stderr)
        raise SystemExit(1)
    real = str(requested_path.resolve())
    copy_real(root, real)
    copy_aliases(root, requested, real)
    # The requested name itself may be a regular file (not a symlink).
    if not requested_path.is_symlink():
        rel = requested_path.relative_to("/")
        dest = root / rel
        ensure_parent(root, dest)
        if not dest.exists():
            copy_real(root, real)
            shutil.copy2(requested_path.resolve(), dest, follow_symlinks=True)


def scan_dependencies(root: Path, path: str) -> None:
    for dep in run_ldd(path):
        if dep in seen_libs:
            continue
        seen_libs.add(dep)
        if not Path(dep).exists():
            continue
        copy_real(root, str(Path(dep).resolve()))
        copy_aliases(root, dep, str(Path(dep).resolve()))
        scan_dependencies(root, dep)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    dest_dir = root / args.dest
    dest_dir.mkdir(parents=True, exist_ok=True)

    for source in args.paths:
        src = Path(source)
        if not src.exists():
            print(f"[-] missing: {source}", file=sys.stderr)
            return 1
        target = dest_dir / src.name
        if target.exists() or target.is_symlink():
            target.unlink()
        # Copy the requested name, resolving symlinks so the target name works
        # even when the original symlink chain is not present in the rootfs.
        shutil.copy2(src.resolve(), target, follow_symlinks=True)
        scan_dependencies(root, str(src.resolve()))
        # Also copy aliases in the original directory (e.g. libfoo.so.1).
        copy_aliases(root, source, str(src.resolve()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
