"""Signed repository index loading and verification for garb."""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .common import GarbError, SCHEMA, warn
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


def fetch_repo_file(url: str, name: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ("", "file"):
        base = Path(parsed.path if parsed.scheme == "file" else url)
        return (base / name).read_bytes()
    with urllib.request.urlopen(f"{url.rstrip('/')}/{name}", timeout=30) as response:
        return response.read()


def validate_index(index: dict, name: str, cached: Path) -> None:
    """Reject unversioned, expired or replayed repository indexes."""
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
    now = int(time.time())
    if expires <= now:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires))
        raise GarbError(
            f"{name}: index expired at {stamp}; regenerate it with 'garb repo-index'"
        )
    cached_index = cached / "index.json"
    if not cached_index.exists():
        return
    try:
        previous = json.loads(cached_index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    previous_version = previous.get("index_version") if isinstance(previous, dict) else None
    if isinstance(previous_version, int) and not isinstance(previous_version, bool):
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
