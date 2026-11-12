"""Signed repository index loading and verification for garb."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .common import (
    GarbError,
    MAX_INDEX_LIFETIME,
    MAX_REPO_INDEX_BYTES,
    SCHEMA,
    warn,
)
from .store import Paths


def read_repo_configs(paths: Paths) -> list[dict]:
    repos = []
    if not paths.repos.is_dir():
        return repos
    for conf in sorted(paths.repos.glob("*.conf")):
        values = {}
        for line in conf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip().lower()] = value.strip().strip('"')
        if "url" not in values:
            warn(f"ignoring {conf}: no url")
            continue
        repos.append({"name": values.get("name", conf.stem), "url": values["url"], "conf": conf})
    return repos


def _source_path(url: str, name: str) -> Path | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ("", "file"):
        base = Path(parsed.path if parsed.scheme == "file" else url)
        return base / name
    return None


def fetch_repo_file(url: str, name: str, max_bytes: int | None = None) -> bytes:
    """Fetch a small repository file with an optional hard size bound."""
    source = _source_path(url, name)
    if source is not None:
        if max_bytes is not None and source.stat().st_size > max_bytes:
            raise GarbError(f"{name} exceeds the {max_bytes}-byte limit")
        return source.read_bytes()
    with urllib.request.urlopen(f"{url.rstrip('/')}/{name}", timeout=30) as response:
        if max_bytes is not None:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_bytes:
                raise GarbError(f"{name} exceeds the {max_bytes}-byte limit")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise GarbError(f"{name} exceeds the {max_bytes}-byte limit")
            return data
        return response.read()


def fetch_repo_file_to(
    url: str, name: str, target: Path, max_bytes: int
) -> tuple[str, int]:
    """Stream a repository file to target and return (sha256, size).

    Package archives can be large enough that reading them into memory is a
    denial-of-service vector. The temporary file stays beside the destination
    so the final rename is atomic on the same filesystem.
    """
    if max_bytes <= 0:
        raise GarbError("download size limit must be positive")
    source = _source_path(url, name)
    if source is not None and source.stat().st_size > max_bytes:
        raise GarbError(f"{name} exceeds the {max_bytes}-byte limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".part", dir=target.parent
    )
    temporary_path = Path(temporary)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, "wb") as output:
            if source is not None:
                reader = open(source, "rb")
            else:
                reader = urllib.request.urlopen(
                    f"{url.rstrip('/')}/{name}", timeout=30
                )
            with reader:
                while True:
                    chunk = reader.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise GarbError(f"{name} exceeds the {max_bytes}-byte limit")
                    digest.update(chunk)
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, target)
        try:
            directory = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        except OSError:
            return digest.hexdigest(), total
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return digest.hexdigest(), total
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def validate_index(index: dict, name: str, cached: Path) -> None:
    """Reject unversioned, expired, overlong or replayed indexes."""
    version = index.get("index_version")
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise GarbError(
            f"{name}: index has no valid index_version; regenerate it with 'garb repo-index'"
        )
    expires = index.get("expires")
    if not isinstance(expires, int) or isinstance(expires, bool):
        raise GarbError(
            f"{name}: index has no expiry timestamp; regenerate it with 'garb repo-index'"
        )
    if not isinstance(index.get("packages"), dict):
        raise GarbError(f"{name}: index has no package map")
    now = int(time.time())
    if expires <= now:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires))
        raise GarbError(
            f"{name}: index expired at {stamp}; regenerate it with 'garb repo-index'"
        )
    if expires > now + MAX_INDEX_LIFETIME:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires))
        raise GarbError(
            f"{name}: index expiry {stamp} is more than "
            f"{MAX_INDEX_LIFETIME // 86400} days in the future; refusing an "
            "unreasonably long-lived signed index"
        )
    cached_index = cached / "index.json"
    if not cached_index.exists():
        return
    try:
        if cached_index.stat().st_size > MAX_REPO_INDEX_BYTES:
            raise GarbError(
                f"{name}: cached index exceeds {MAX_REPO_INDEX_BYTES} bytes; "
                "remove the cache only after verifying the repository and retry"
            )
        previous = json.loads(cached_index.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GarbError(
            f"{name}: cached index is unreadable ({exc}); remove the cache "
            "only after verifying the repository and retry"
        ) from exc
    previous_version = previous.get("index_version") if isinstance(previous, dict) else None
    if not isinstance(previous_version, int) or isinstance(previous_version, bool) or previous_version <= 0:
        raise GarbError(
            f"{name}: cached index has no valid index_version; remove the cache "
            "only after verifying the repository and retry"
        )
    if version < previous_version:
        raise GarbError(
            f"{name}: refusing a replayed index (version {version} is older "
            f"than the cached version {previous_version})"
        )


def verify_signature(index: bytes, signature: bytes, public_key: Path) -> None:
    if not public_key.exists():
        raise GarbError(f"trusted public key is missing: {public_key}")
    with tempfile.TemporaryDirectory() as scratch:
        index_path = Path(scratch) / "index.json"
        sig_path = Path(scratch) / "index.json.sig"
        index_path.write_bytes(index)
        sig_path.write_bytes(signature)
        result = subprocess.run(
            [
                "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key),
                "-rawin", "-in", str(index_path), "-sigfile", str(sig_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GarbError(f"repository signature verification failed: {result.stderr.strip()}")


def sign_bytes(data: bytes, private_key: Path) -> bytes:
    with tempfile.TemporaryDirectory() as scratch:
        data_path = Path(scratch) / "data"
        sig_path = Path(scratch) / "data.sig"
        data_path.write_bytes(data)
        result = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(private_key), "-rawin",
             "-in", str(data_path), "-out", str(sig_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise GarbError(f"signing failed: {result.stderr.strip()}")
        return sig_path.read_bytes()


def load_repo_priorities(paths: Paths) -> dict[str, int]:
    if not paths.preferences.is_file():
        return {}
    priors: dict[str, int] = {}
    for line in paths.preferences.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            try:
                priors[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return priors


def load_indexes(paths: Paths) -> dict:
    packages: dict = {}
    if not paths.cache.is_dir():
        return packages
    priors = load_repo_priorities(paths)
    index_files = sorted(
        paths.cache.glob("repos/*/index.json"),
        key=lambda p: priors.get(p.parent.name, 500),
        reverse=True,
    )
    for index_path in index_files:
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            warn(f"ignoring unreadable index: {index_path}")
            continue
        if not isinstance(data, dict):
            warn(f"ignoring index that is not a JSON object: {index_path}")
            continue
        if data.get("schema") != SCHEMA:
            warn(f"ignoring index with unsupported schema {data.get('schema')!r}: {index_path}")
            continue
        for name, entry in data.get("packages", {}).items():
            entry = dict(entry)
            entry["_repo"] = index_path.parent.name
            packages.setdefault(name, entry)
    return packages
