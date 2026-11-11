"""Unit tests for the garblib package extracted from bin/garb."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from garblib.archive import (  # noqa: E402
    build_package,
    extract_tree,
    read_metadata,
    write_canonical_archive,
)
from garblib.backends import (  # noqa: E402
    backend_kind,
    conflict_paths,
    protected_overwrite,
)
from garblib.common import (  # noqa: E402
    GarbError,
    normalise_member,
    parse_mode,
    safe_symlink_target,
    sha256_file,
)
from garblib.delta import validate_delta_tree  # noqa: E402
from garblib.deps import match_version, resolve_dependencies  # noqa: E402
from garblib.repo import sign_bytes, validate_index, verify_signature  # noqa: E402
from garblib.store import Database, Paths  # noqa: E402


def test_common_rejects_unsafe_paths_and_modes(tmp_path: Path) -> None:
    assert normalise_member("./usr/bin/tool") == "usr/bin/tool"
    for bad in ("/etc/passwd", "../escape", "usr/../../escape", ""):
        with pytest.raises(GarbError):
            normalise_member(bad)
    assert safe_symlink_target("../lib/tool", "usr/bin") == "../lib/tool"
    with pytest.raises(GarbError):
        safe_symlink_target("../../../etc/passwd", "usr/bin")
    assert parse_mode("0755") == 0o755
    sample = tmp_path / "sample"
    sample.write_bytes(b"abc")
    assert sha256_file(sample) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_store_confines_target_paths_and_fails_closed_on_corrupt_db(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    assert paths.inside("etc/example.conf") == (tmp_path / "etc/example.conf").resolve()
    with pytest.raises(GarbError):
        paths.inside("../outside")
    paths.db.parent.mkdir(parents=True)
    paths.db.write_text("{", encoding="utf-8")
    with pytest.raises(GarbError, match="corrupt or unreadable"):
        Database(paths)


def test_repo_rejects_expired_and_replayed_indexes(tmp_path: Path) -> None:
    now = int(time.time())
    validate_index({"index_version": 2, "expires": now + 60}, "test", tmp_path)
    with pytest.raises(GarbError, match="expired"):
        validate_index({"index_version": 2, "expires": now - 60}, "test", tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "index.json").write_text(
        json.dumps({"index_version": 3, "expires": now + 60}), encoding="utf-8"
    )
    with pytest.raises(GarbError, match="replayed"):
        validate_index({"index_version": 2, "expires": now + 60}, "test", cache)


def test_repo_signature_roundtrip(tmp_path: Path) -> None:
    key = tmp_path / "release.key"
    public = tmp_path / "release.pub"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(key)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(public)],
        check=True,
        capture_output=True,
    )
    payload = b'{"index_version": 1}'
    signature = sign_bytes(payload, key)
    verify_signature(payload, signature, public)
    with pytest.raises(GarbError):
        verify_signature(payload + b"x", signature, public)


def test_archive_build_extract_and_canonical_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    package = tmp_path / "src"
    (package / "root/usr/bin").mkdir(parents=True)
    (package / "root/var/empty").mkdir(parents=True)
    (package / "root/usr/bin/hello").write_text("hello\n", encoding="utf-8")
    (package / "root/usr/bin/hello-link").symlink_to("hello")
    manifest = package / "Garbfile"
    manifest.write_text(
        '[package]\nname = "hello"\nversion = "1.0"\nrelease = 1\n'
        'description = "test package"\nlicense = "MIT"\n',
        encoding="utf-8",
    )

    archive = build_package(manifest, tmp_path / "out")
    metadata = read_metadata(archive)
    assert metadata["name"] == "hello"
    assert metadata["schema"] == 1

    tree = tmp_path / "tree"
    entries = extract_tree(archive, tree, manifest=True)
    assert (tree / "var/empty").is_dir()
    assert (tree / "usr/bin/hello-link").is_symlink()
    assert os.readlink(tree / "usr/bin/hello-link") == "hello"

    canonical = tmp_path / "canonical.garb"
    write_canonical_archive(entries, tree, canonical, max(entry["mtime"] for entry in entries))
    assert sha256_file(canonical) == sha256_file(archive)


def test_archive_extract_tree_rejects_traversal(tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("../escape")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(GarbError, match="parent traversal"):
        extract_tree(evil, tmp_path / "tree")
    assert not (tmp_path / "escape").exists()


def test_deps_match_and_resolve_in_order(tmp_path: Path) -> None:
    assert match_version("1.3", ">=", "1.2")
    assert not match_version("1.1", ">=", "1.2")
    db = Database(Paths(tmp_path))
    index = {
        "app": {"version": "1.0", "dependencies": ["lib>=1.2"]},
        "lib": {"version": "1.3"},
    }
    assert resolve_dependencies(["app"], index, db) == ["lib", "app"]


def test_backends_protect_sensitive_paths() -> None:
    assert backend_kind("/usr/bin/pacman") == "pacman"
    with pytest.raises(GarbError):
        backend_kind("/usr/bin/dpkg")
    assert conflict_paths("error: /etc/example exists in filesystem\n") == ["/etc/example"]
    assert protected_overwrite("/etc/shadow")
    assert protected_overwrite("/etc/sudoers.d/99-local")
    assert not protected_overwrite("/etc/hosts")


def test_delta_tree_rejects_invalid_entries() -> None:
    entries = validate_delta_tree(
        [
            {"path": "usr/bin/hello", "type": "file", "mode": "0755", "sha256": "a" * 64},
            {"path": "usr/bin/hello-link", "type": "symlink", "target": "hello"},
            {"path": "var/empty", "type": "dir", "mode": "0755"},
        ]
    )
    assert entries[0]["mode"] == 0o755
    with pytest.raises(GarbError):
        validate_delta_tree([{"path": "../escape", "type": "dir"}])
    with pytest.raises(GarbError):
        validate_delta_tree(
            [{"path": "usr/bin/link", "type": "symlink", "target": "/etc/passwd"}]
        )
