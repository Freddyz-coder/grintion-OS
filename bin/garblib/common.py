"""Shared constants and fail-closed helpers for garb."""
from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path, PurePosixPath

VERSION = "0.10.1"
SCHEMA = 1
DEFAULT_DB = "var/lib/garb/db.json"
DEFAULT_REPOS = "etc/garb/repos.d"
DEFAULT_KEYS = "etc/garb/keys"
DEFAULT_CACHE = "var/cache/garb"
DEFAULT_TMP = "var/lib/garb/tmp"
METADATA_NAME = "GARB_METADATA.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class GarbError(Exception):
    pass


def log(message: str) -> None:
    print(f"[*] {message}")


def warn(message: str) -> None:
    print(f"[!] {message}", file=sys.stderr)


def die(message: str) -> None:
    print(f"[-] {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def epoch() -> int:
    try:
        return int(os.environ.get("SOURCE_DATE_EPOCH", "") or time.time())
    except ValueError:
        return int(time.time())


def normalise_member(name: str) -> str:
    """Return a safe relative POSIX path or raise."""
    if not name or "\x00" in name:
        raise GarbError("empty or NUL-containing archive member")
    pure = PurePosixPath(name)
    if pure.is_absolute():
        raise GarbError(f"absolute path in archive: {name}")
    parts = []
    for part in pure.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise GarbError(f"parent traversal in archive: {name}")
        parts.append(part)
    if not parts:
        raise GarbError(f"invalid archive member: {name}")
    return "/".join(parts)


def safe_symlink_target(link: str, base_dir: str = "") -> str:
    if not link or "\x00" in link or os.path.isabs(link):
        raise GarbError(f"unsafe symlink target: {link!r}")
    depth = 0
    for part in (PurePosixPath(base_dir) / link).parts:
        if part in ("", "."):
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                raise GarbError(f"symlink escapes the root: {link!r}")
        else:
            depth += 1
    return link


def parse_mode(value: object, default: int = 0o644) -> int:
    if isinstance(value, int):
        return value & 0o7777
    if isinstance(value, str):
        try:
            return int(value, 8) & 0o7777
        except ValueError:
            pass
    return default
