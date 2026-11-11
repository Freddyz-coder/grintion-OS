"""Delta archive creation and verified reconstruction for garb."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from .archive import (
    confined_tree_path,
    extract_tree,
    validate_delta_tree,
    write_canonical_archive,
)
from .common import (
    GarbError,
    METADATA_NAME,
    SCHEMA,
    SHA256_RE,
    die,
    epoch,
    log,
    sha256_file,
)
from .repo import verify_signature

DELTA_METADATA_NAME = "GARB_DELTA_METADATA.json"
DELTA_FORMAT = "garb-delta-v2"


def cmd_delta_create(args: argparse.Namespace) -> None:
    old_archive = Path(args.old)
    new_archive = Path(args.new)
    out_delta = Path(args.out)
    if not old_archive.is_file() or not new_archive.is_file():
        die("old and new archives must exist")

    work = Path(tempfile.mkdtemp(prefix="garb-delta-"))
    old_tree = work / "old"
    new_tree = work / "new"
    delta_tree = work / "delta"
    try:
        old_entries = extract_tree(old_archive, old_tree, manifest=True)
        new_entries = extract_tree(new_archive, new_tree, manifest=True)
        if not any(entry["path"] == METADATA_NAME for entry in new_entries):
            die(f"new archive has no {METADATA_NAME}")
        metadata = json.loads((new_tree / METADATA_NAME).read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            die("package metadata is not a JSON object")

        # A delta is only safe to verify against the signed index if applying
        # it reproduces the exact published archive bytes. Refuse a new archive
        # written by an older, non-deterministic build path.
        new_mtime = max(entry["mtime"] for entry in new_entries)
        canonical = work / "canonical.garb"
        write_canonical_archive(new_entries, new_tree, canonical, new_mtime)
        if sha256_file(canonical) != sha256_file(new_archive):
            die("new archive is not in canonical garb format; rebuild it with this garb version")

        old_files = {
            entry["path"]: entry["sha256"]
            for entry in old_entries if entry["type"] == "file"
        }
        modified: list[str] = []
        for entry in new_entries:
            if entry["type"] != "file":
                continue
            if old_files.get(entry["path"]) == entry["sha256"]:
                continue
            destination = delta_tree / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(new_tree / entry["path"], destination)
            modified.append(entry["path"])

        new_paths = {entry["path"] for entry in new_entries}
        meta = {
            "format": DELTA_FORMAT,
            "package": metadata.get("name"),
            "version": metadata.get("version"),
            "release": metadata.get("release", 1),
            "old_sha256": sha256_file(old_archive),
            "new_sha256": sha256_file(new_archive),
            "mtime": new_mtime,
            "tree": new_entries,
            "modified": modified,
            "deleted": sorted(set(old_files) - new_paths),
        }
        (delta_tree / DELTA_METADATA_NAME).write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        delta_entries = [
            {
                "path": DELTA_METADATA_NAME,
                "type": "file",
                "mode": 0o644,
                "sha256": sha256_file(delta_tree / DELTA_METADATA_NAME),
            }
        ] + [entry for entry in new_entries if entry["path"] in set(modified)]
        write_canonical_archive(delta_entries, delta_tree, out_delta, epoch())
    finally:
        shutil.rmtree(work, ignore_errors=True)

    log(f"created delta update {out_delta} ({out_delta.stat().st_size} bytes)")


def cmd_delta_apply(args: argparse.Namespace) -> None:
    old_archive = Path(args.old)
    delta_file = Path(args.delta)
    out_archive = Path(args.out)
    if not old_archive.is_file():
        die(f"old archive not found: {old_archive}")
    if not delta_file.is_file():
        die(f"delta archive not found: {delta_file}")

    work = Path(tempfile.mkdtemp(prefix="garb-apply-"))
    old_tree = work / "old"
    delta_tree = work / "delta"
    out_tree = work / "out"
    output_tmp = out_archive.with_name(out_archive.name + ".tmp")
    try:
        extract_tree(old_archive, old_tree)
        extract_tree(delta_file, delta_tree)
        meta_file = delta_tree / DELTA_METADATA_NAME
        if not meta_file.is_file() or meta_file.is_symlink():
            die(f"delta is missing {DELTA_METADATA_NAME}")
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            die(f"delta metadata is unreadable: {exc}")
        if not isinstance(meta, dict):
            die("delta metadata is not a JSON object")
        if meta.get("format") != DELTA_FORMAT:
            die(
                f"unsupported delta format {meta.get('format')!r}; "
                "recreate it with this garb version"
            )
        tree = validate_delta_tree(meta.get("tree"))
        expected_sha = meta.get("new_sha256")
        if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
            die("delta metadata has no valid new_sha256")
        mtime = meta.get("mtime")
        if not isinstance(mtime, int) or isinstance(mtime, bool) or mtime < 0:
            die("delta metadata has no valid mtime")

        declared_files = {entry["path"] for entry in tree if entry["type"] == "file"}
        for path in delta_tree.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                continue
            rel = path.relative_to(delta_tree).as_posix()
            if rel == DELTA_METADATA_NAME:
                continue
            if rel not in declared_files:
                raise GarbError(f"delta contains an undeclared file: {rel}")

        out_tree.mkdir(parents=True, exist_ok=True)
        for entry in tree:
            rel = entry["path"]
            target = confined_tree_path(out_tree, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry["type"] == "dir":
                if target.exists() and not target.is_dir():
                    raise GarbError(f"cannot create directory: {rel}")
                target.mkdir(exist_ok=True)
                os.chmod(target, entry["mode"])
                continue
            if target.is_dir() and not target.is_symlink():
                raise GarbError(f"cannot replace directory with a file: {rel}")
            if target.exists() or target.is_symlink():
                target.unlink()
            if entry["type"] == "symlink":
                os.symlink(entry["target"], target)
                continue
            source = delta_tree / rel
            if not source.is_file() or source.is_symlink():
                source = old_tree / rel
            if not source.is_file() or source.is_symlink():
                raise GarbError(f"delta has no payload for {rel}")
            if sha256_file(source) != entry["sha256"]:
                raise GarbError(f"payload hash mismatch: {rel}")
            shutil.copyfile(source, target)
            os.chmod(target, entry["mode"])

        write_canonical_archive(tree, out_tree, output_tmp, mtime)
        actual_sha = sha256_file(output_tmp)
        if actual_sha != expected_sha:
            raise GarbError(
                "reconstructed archive does not match the delta's new_sha256 "
                f"(expected {expected_sha}, got {actual_sha})"
            )

        # A delta is untrusted input. Its metadata hash only proves internal
        # consistency; the authoritative value must come from a signed index.
        index_path = Path(args.index)
        key_path = Path(args.key)
        signature_path = Path(str(index_path) + ".sig")
        if not index_path.is_file():
            die(f"signed index not found: {index_path}")
        if not signature_path.is_file():
            die(f"index signature not found: {signature_path}")
        verify_signature(index_path.read_bytes(), signature_path.read_bytes(), key_path)
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            die(f"signed index is unreadable: {exc}")
        if not isinstance(index, dict) or index.get("schema") != SCHEMA:
            die("signed index has an unexpected schema")
        package = args.package or meta.get("package")
        if not isinstance(package, str) or not package:
            die("delta metadata does not name a package; pass --package")
        entry = index.get("packages", {}).get(package)
        if not isinstance(entry, dict):
            die(f"package {package} is not present in the signed index")
        if entry.get("sha256") != actual_sha:
            raise GarbError(
                f"reconstructed {package} archive does not match the signed index "
                f"(expected {entry.get('sha256')}, got {actual_sha})"
            )

        out_archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(output_tmp, out_archive)
    finally:
        output_tmp.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)

    log(f"reconstructed and verified archive {out_archive} from delta")
