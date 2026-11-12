"""Shared constants and fail-closed helpers for garb."""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
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

# Resource limits are part of the parser contract: a repository key can sign a
# malformed archive, so signature verification alone is not a size or memory
# guarantee. These are deliberately generous for native packages and small
# enough to stop a decompression bomb from filling the target root.
MAX_PATH_LENGTH = 4096
MAX_ARCHIVE_MEMBERS = 200_000
MAX_EXTRACTED_BYTES = 8 * 1024**3
MAX_METADATA_BYTES = 4 * 1024 * 1024
MAX_DECLARED_FILES = 200_000
MAX_REPO_INDEX_BYTES = 64 * 1024 * 1024
MAX_REPO_SIGNATURE_BYTES = 16 * 1024
MAX_PACKAGE_BYTES = 2 * 1024**3
MAX_INDEX_LIFETIME = 90 * 86400
MIN_FREE_BYTES = 64 * 1024**2


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
    if len(name) > MAX_PATH_LENGTH:
        raise GarbError(f"archive member path is too long: {len(name)} bytes")
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
    rel = "/".join(parts)
    if len(rel) > MAX_PATH_LENGTH:
        raise GarbError(f"archive member path is too long: {len(rel)} bytes")
    return rel


def safe_symlink_target(link: str, base_dir: str = "") -> str:
    if not link or "\x00" in link or os.path.isabs(link):
        raise GarbError(f"unsafe symlink target: {link!r}")
    if len(link) > MAX_PATH_LENGTH:
        raise GarbError(f"symlink target is too long: {len(link)} bytes")
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


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Replace a file atomically, including a directory fsync.

    Repository indexes and security policy files must never be visible in a
    half-written state if the machine loses power during the write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        try:
            directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError:
            return
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str, mode: int = 0o644) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)
