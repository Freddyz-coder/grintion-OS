#!/usr/bin/env python3
"""Create a deterministic gzip-compressed newc initramfs.

Usage: mkinitramfs.py <root-directory> <output.img> [--epoch N]

All entries are owned by uid/gid 0, mtimes are fixed, and the gzip header has
no timestamp or filename. Device nodes are intentionally rejected: devtmpfs
creates them at boot. Sockets and FIFOs are skipped.
"""
from __future__ import annotations

import argparse
import gzip
import os
import stat
import struct
import sys
from pathlib import Path

# Directories whose contents are supplied by the kernel at runtime.
SKIP_CONTENTS = {"dev", "proc", "sys", "run"}


def add_entry(
    out: bytearray,
    name: str,
    mode: int,
    data: bytes,
    ino: int,
    epoch: int,
) -> None:
    name_bytes = name.encode("utf-8")
    name_size = len(name_bytes) + 1
    header = struct.pack(
        "6s" + "8s" * 13,
        b"070701",
        f"{ino:08x}".encode(),
        f"{mode:08x}".encode(),
        b"00000000",  # uid
        b"00000000",  # gid
        b"00000001",  # nlink
        f"{epoch:08x}".encode(),
        f"{len(data):08x}".encode(),
        b"00000000",  # devmajor
        b"00000000",  # devminor
        b"00000000",  # rdevmajor
        b"00000000",  # rdevminor
        f"{name_size:08x}".encode(),
        b"00000000",  # check
    )
    out += header
    out += name_bytes + b"\0"
    out += b"\0" * ((-len(out)) % 4)
    out += data
    out += b"\0" * ((-len(data)) % 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("output")
    parser.add_argument("--epoch", type=int, default=int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600")))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[-] not a directory: {root}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[str, Path]] = []
    for current, dirs, files in os.walk(root):
        rel_current = Path(current).relative_to(root)
        if rel_current.parts and rel_current.parts[0] in SKIP_CONTENTS:
            dirs[:] = []
            files = []
        dirs.sort()
        files.sort()
        for name in dirs + files:
            path = Path(current) / name
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] in SKIP_CONTENTS:
                continue
            entries.append((str(rel), path))

    entries.sort(key=lambda item: item[0])

    # The kernel mounts devtmpfs, proc, sysfs and tmpfs over these paths. They
    # must exist as directories even though their contents are runtime state.
    runtime_dirs = ["dev", "proc", "sys", "run"]
    existing = {rel for rel, _ in entries}
    for name in runtime_dirs:
        if name not in existing:
            entries.append((name, root / name))
    entries.sort(key=lambda item: item[0])

    out = bytearray()
    ino = 1
    for rel, path in entries:
        if rel in runtime_dirs and not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        try:
            info = path.lstat()
        except OSError as exc:
            print(f"[-] stat failed: {path}: {exc}", file=sys.stderr)
            return 1
        mode = info.st_mode
        if stat.S_ISLNK(mode):
            data = os.readlink(path).encode("utf-8")
            entry_mode = 0o120777
            name = rel
        elif stat.S_ISDIR(mode):
            data = b""
            entry_mode = 0o040755 | (stat.S_IMODE(mode) & 0o777)
            name = rel
        elif stat.S_ISREG(mode):
            data = path.read_bytes()
            entry_mode = 0o100000 | (stat.S_IMODE(mode) & 0o7777)
            name = rel
        elif stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            print(f"[-] device node not allowed in initramfs: {rel}", file=sys.stderr)
            return 1
        else:
            print(f"[!] skipping special file: {rel}", file=sys.stderr)
            continue

        add_entry(out, name, entry_mode, data, ino, args.epoch)
        ino += 1

    add_entry(out, "TRAILER!!!", 0, b"", ino, args.epoch)
    out += b"\0" * ((-len(out)) % 512)

    with open(output, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(out)

    print(f"[+] {output} ({output.stat().st_size} bytes, {len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
