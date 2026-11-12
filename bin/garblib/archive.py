"""Safe package archive extraction, verification and construction for garb."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
import time
import tomllib
from pathlib import Path, PurePosixPath

from .common import (
    GarbError,
    MAX_ARCHIVE_MEMBERS,
    MAX_DECLARED_FILES,
    MAX_EXTRACTED_BYTES,
    MAX_METADATA_BYTES,
    METADATA_NAME,
    MIN_FREE_BYTES,
    SCHEMA,
    SHA256_RE,
    epoch,
    normalise_member,
    parse_mode,
    safe_symlink_target,
    sha256_file,
    warn,
)
from .store import Database, Paths


def validate_archive(archive: Path) -> dict:
    """Validate the complete member table before any file is extracted.

    Signature verification proves who produced an archive, not that it is
    bounded or structurally sane. Scanning first means a duplicate path, an
    oversized member or a decompression bomb cannot leave a partially
    extracted tree behind.
    """
    metadata: dict | None = None
    seen: set[str] = set()
    total = 0
    members = 0
    with tarfile.open(archive, "r:*") as tar:
        for member in tar:
            members += 1
            if members > MAX_ARCHIVE_MEMBERS:
                raise GarbError(
                    f"archive has more than {MAX_ARCHIVE_MEMBERS} members; refusing it"
                )
            rel = normalise_member(member.name)
            if rel in seen:
                raise GarbError(f"duplicate archive member: {rel}")
            seen.add(rel)
            if member.isreg():
                if member.size < 0:
                    raise GarbError(f"negative member size: {rel}")
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise GarbError(
                        "archive expands beyond the allowed size limit "
                        f"({MAX_EXTRACTED_BYTES} bytes)"
                    )
            verify_member(member)
            if rel != METADATA_NAME:
                continue
            if not member.isreg():
                raise GarbError("metadata member is not a regular file")
            if member.size > MAX_METADATA_BYTES:
                raise GarbError(
                    f"package metadata exceeds {MAX_METADATA_BYTES} bytes"
                )
            handle = tar.extractfile(member)
            if handle is None:
                raise GarbError("metadata member is not readable")
            try:
                parsed = json.loads(handle.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GarbError(f"package metadata is not valid JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise GarbError("package metadata is not a JSON object")
            metadata = parsed
    if metadata is None:
        raise GarbError(f"missing {METADATA_NAME} in {archive}")
    if metadata.get("schema", SCHEMA) != SCHEMA:
        raise GarbError("unsupported package schema")
    return metadata


def read_metadata(archive: Path) -> dict:
    return validate_archive(archive)


def verify_member(member: tarfile.TarInfo) -> None:
    rel = normalise_member(member.name)
    if member.isdir():
        return
    if member.isreg():
        return
    if member.issym():
        safe_symlink_target(member.linkname, str(PurePosixPath(rel).parent))
        return
    raise GarbError(f"unsupported archive member type: {rel}")


def extract_staged(archive: Path, staging: Path) -> tuple[dict, list[dict]]:
    metadata = validate_archive(archive)
    members: list[dict] = []
    with tarfile.open(archive, "r:*") as tar:
        for member in tar:
            if normalise_member(member.name) == METADATA_NAME:
                continue
            verify_member(member)
            rel = normalise_member(member.name)
            dest = confined_tree_path(staging, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                if dest.is_symlink() or (dest.exists() and not dest.is_dir()):
                    raise GarbError(f"archive directory conflicts with an existing entry: {rel}")
                dest.mkdir(exist_ok=True)
                continue
            if member.issym():
                if dest.exists() or dest.is_symlink():
                    if dest.is_dir() and not dest.is_symlink():
                        raise GarbError(f"archive symlink conflicts with a directory: {rel}")
                    dest.unlink()
                os.symlink(member.linkname, dest)
                members.append({"path": rel, "type": "symlink", "target": member.linkname})
                continue
            if dest.is_dir() and not dest.is_symlink():
                raise GarbError(f"archive file conflicts with a directory: {rel}")
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            handle = tar.extractfile(member)
            if handle is None:
                raise GarbError(f"cannot read member: {rel}")
            with open(dest, "xb") as output:
                shutil.copyfileobj(handle, output)
            members.append({"path": rel, "type": "file"})
    return metadata, members


def verify_staged(staging: Path, metadata: dict) -> list[dict]:
    declared = metadata.get("files")
    if not isinstance(declared, list) or not declared:
        raise GarbError("package metadata has no file list")
    if len(declared) > MAX_DECLARED_FILES:
        raise GarbError(
            f"package declares more than {MAX_DECLARED_FILES} files; refusing it"
        )
    by_path = {}
    total = 0
    for item in declared:
        if not isinstance(item, dict):
            raise GarbError("package metadata has a malformed file entry")
        rel = normalise_member(str(item.get("path", "")))
        if rel == METADATA_NAME:
            raise GarbError(f"package tries to install metadata as a payload file: {rel}")
        if rel in by_path:
            raise GarbError(f"duplicate declared file: {rel}")
        if item.get("type") not in ("file", "symlink"):
            raise GarbError(f"unsupported declared file type for {rel}: {item.get('type')!r}")
        by_path[rel] = item
    seen = set()
    for rel, item in by_path.items():
        staged = staging / rel
        if item.get("type") == "symlink":
            if not staged.is_symlink():
                raise GarbError(f"missing symlink: {rel}")
            safe_symlink_target(item.get("target", ""), str(PurePosixPath(rel).parent))
            if os.readlink(staged) != item.get("target"):
                raise GarbError(f"symlink target mismatch: {rel}")
        else:
            if not staged.is_file() or staged.is_symlink():
                raise GarbError(f"missing file: {rel}")
            size = staged.stat().st_size
            total += size
            if total > MAX_EXTRACTED_BYTES:
                raise GarbError("declared payload exceeds the allowed size limit")
            digest = sha256_file(staged)
            if digest != item.get("sha256"):
                raise GarbError(f"hash mismatch: {rel}")
            mode = parse_mode(item.get("mode"), 0o644)
            if mode & (stat.S_ISUID | stat.S_ISGID):
                raise GarbError(
                    f"package requests a setuid/setgid file: {rel} "
                    "(packages may not install privileged binaries)"
                )
        seen.add(rel)
    # Anything staged that is not declared is a malformed package. Check
    # is_symlink() before is_dir(): a symlink to a directory otherwise looks
    # like a declared container and escapes the undeclared-entry check.
    for path in staging.rglob("*"):
        rel = str(path.relative_to(staging))
        if rel in seen:
            continue
        if path.is_symlink() or path.is_file():
            raise GarbError(f"undeclared file in package: {rel}")
        if path.is_dir():
            continue
        raise GarbError(f"unsupported staged entry in package: {rel}")
    return declared


def ensure_free_space(root: Path, staging: Path, files: list[dict]) -> None:
    """Refuse a commit that would exhaust the target filesystem.

    Files are moved from staging, but the database, journal and filesystem
    metadata still need room. A corrupt package must not be able to turn a
    failed install into a full root filesystem.
    """
    required = 0
    for item in files:
        rel = normalise_member(item["path"])
        if item.get("type") != "file":
            continue
        try:
            required += (staging / rel).stat().st_size
        except OSError as exc:
            raise GarbError(f"cannot measure staged file {rel}: {exc}") from exc
    try:
        available = shutil.disk_usage(root).free
    except OSError as exc:
        raise GarbError(f"cannot determine free space for {root}: {exc}") from exc
    if available < required + MIN_FREE_BYTES:
        raise GarbError(
            f"not enough free space under {root}: need {required + MIN_FREE_BYTES} bytes, "
            f"have {available}"
        )


def remove_path(path: Path) -> None:
    """Remove a file, symlink or directory tree if it exists."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def reverse_dependents(db: Database, name: str, ignore: set[str] | None = None) -> list[str]:
    skip = ignore or set()
    return sorted(
        package
        for package, entry in db.data["packages"].items()
        if package != name
        and package not in skip
        and name in entry.get("dependencies", [])
    )


def file_conflicts(db: Database, name: str, files: list[dict]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for package, entry in db.data["packages"].items():
        if package == name:
            continue
        for item in entry.get("files", []):
            owners.setdefault(item["path"], package)
    conflicts = {}
    for item in files:
        owner = owners.get(item["path"])
        if owner:
            conflicts[item["path"]] = owner
    return conflicts


def commit_package(paths: Paths, staging: Path, metadata: dict, archive: Path) -> dict:
    files = verify_staged(staging, metadata)
    ensure_free_space(paths.root, staging, files)
    paths.tmp.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="garb-backup-", dir=paths.tmp))
    installed: list[dict] = []
    backup_kept = False
    try:
        for item in files:
            rel = normalise_member(item["path"])
            src = staging / rel
            dst = paths.inside(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() or dst.is_symlink():
                saved = backup / rel
                saved.parent.mkdir(parents=True, exist_ok=True)
                os.replace(dst, saved)
            if item.get("type") == "symlink":
                os.symlink(item["target"], dst)
            else:
                os.replace(src, dst)
                mode = parse_mode(item.get("mode"), 0o644) & ~(stat.S_ISUID | stat.S_ISGID)
                os.chmod(dst, mode)
            installed.append(item)
    except Exception as exc:
        problems: list[str] = []
        for item in reversed(installed):
            try:
                remove_path(paths.inside(item["path"]))
            except OSError as cleanup_exc:
                problems.append(f"remove {item['path']}: {cleanup_exc}")
        for saved in sorted(backup.rglob("*"), key=lambda path: len(path.parts)):
            if not (saved.is_file() or saved.is_symlink()):
                continue
            rel = str(saved.relative_to(backup))
            dst = paths.inside(rel)
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                # A non-empty directory at the destination used to make
                # os.replace fail, after which the backup was deleted anyway.
                remove_path(dst)
                os.replace(saved, dst)
            except OSError as restore_exc:
                problems.append(f"restore {rel}: {restore_exc}")
        if problems:
            backup_kept = True
            warn(f"rollback incomplete; backups kept in {backup}")
            for problem in problems:
                warn(f"  {problem}")
        raise GarbError(f"transaction rolled back: {exc}") from exc
    finally:
        if not backup_kept:
            shutil.rmtree(backup, ignore_errors=True)

    return {
        "name": metadata["name"],
        "version": metadata.get("version", "0"),
        "release": metadata.get("release", 1),
        "description": metadata.get("description", ""),
        "arch": metadata.get("arch", ["x86_64"]),
        "dependencies": metadata.get("dependencies", []),
        "files": files,
        "archive_sha256": sha256_file(archive),
        "installed_at": int(time.time()),
    }


def read_garbfile(path: Path) -> dict:
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    package = data.get("package", {})
    if "name" not in package:
        raise GarbError(f"{path}: [package] name is required")
    deps = data.get("dependencies", {}).get("runtime", [])
    return {
        "name": package["name"],
        "version": str(package.get("version", "0")),
        "release": int(package.get("release", 1)),
        "description": package.get("description", ""),
        "license": package.get("license", ""),
        "arch": package.get("arch", ["x86_64"]),
        "dependencies": deps,
        "build": data.get("build", {}),
        "source": path,
    }


def build_package(manifest: Path, output_dir: Path) -> Path:
    meta = read_garbfile(manifest)
    source_root = manifest.parent / "root"
    files = []
    if source_root.is_dir():
        for path in sorted(source_root.rglob("*")):
            rel = str(path.relative_to(source_root))
            # Check is_symlink() before is_dir(): is_dir() follows links, so a
            # symlink to a directory used to be dropped silently.
            if path.is_symlink():
                target = os.readlink(path)
                safe_symlink_target(target, str(PurePosixPath(rel).parent))
                files.append({"path": rel, "type": "symlink", "target": target})
            elif path.is_dir():
                continue
            elif path.is_file():
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode & (stat.S_ISUID | stat.S_ISGID):
                    raise GarbError(
                        f"{manifest}: refusing to package setuid/setgid file: {rel}"
                    )
                files.append({
                    "path": rel,
                    "type": "file",
                    "sha256": sha256_file(path),
                    "mode": f"{mode:04o}",
                })
    if meta["build"]:
        warn(f"{manifest}: [build] commands are not executed by garb 1.0; "
             "package the resulting tree under root/ instead")
    metadata = {
        "schema": SCHEMA,
        "name": meta["name"],
        "version": meta["version"],
        "release": meta["release"],
        "description": meta["description"],
        "license": meta["license"],
        "arch": meta["arch"],
        "dependencies": meta["dependencies"],
        "files": files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{meta['name']}-{meta['version']}-{meta['release']}.garb"
    stamp = epoch()
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            payload = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8") + b"\n"
            info = tarfile.TarInfo(METADATA_NAME)
            info.size = len(payload)
            info.mtime = stamp
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(payload))
            if source_root.is_dir():
                for path in sorted(source_root.rglob("*")):
                    rel = str(path.relative_to(source_root))
                    info = tar.gettarinfo(str(path), arcname=rel)
                    info.mtime = stamp
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    if path.is_symlink() or path.is_dir():
                        tar.addfile(info)
                    else:
                        with open(path, "rb") as handle:
                            tar.addfile(info, handle)
    archive.write_bytes(raw.getvalue())
    return archive


def confined_tree_path(root: Path, rel: str) -> Path:
    """Return root/rel after proving the resolved parent stays inside root."""
    rel = normalise_member(rel)
    root = root.resolve()
    target = root / rel
    parent = target.parent.resolve()
    if parent != root and root not in parent.parents:
        raise GarbError(f"archive member escapes the extraction root: {rel}")
    return target


def extract_tree(archive: Path, dest: Path, *, manifest: bool = False) -> list[dict]:
    """Safely extract an archive tree and optionally return its member manifest.

    No tarfile.extractall path is used: every member is normalised, symlinks
    are confined to the extraction root, and special files are rejected by
    verify_member(). Directories and symlinks are preserved so a rebuilt
    package does not lose empty directories or directory symlinks.
    """
    entries: list[dict] = []
    seen: set[str] = set()
    total = 0
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tar:
        for count, member in enumerate(tar, start=1):
            if count > MAX_ARCHIVE_MEMBERS:
                raise GarbError(
                    f"archive has more than {MAX_ARCHIVE_MEMBERS} members; refusing it"
                )
            verify_member(member)
            rel = normalise_member(member.name)
            if rel in seen:
                raise GarbError(f"duplicate archive member: {rel}")
            seen.add(rel)
            if member.isreg():
                if member.size < 0:
                    raise GarbError(f"negative member size: {rel}")
                total += member.size
                if total > MAX_EXTRACTED_BYTES:
                    raise GarbError(
                        "archive expands beyond the allowed size limit "
                        f"({MAX_EXTRACTED_BYTES} bytes)"
                    )
            target = confined_tree_path(dest, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = member.mode & 0o7777
            if member.isdir():
                if target.is_symlink() or (target.exists() and not target.is_dir()):
                    raise GarbError(f"archive directory conflicts with an existing entry: {rel}")
                target.mkdir(exist_ok=True)
                os.chmod(target, mode)
                if manifest:
                    entries.append({
                        "path": rel, "type": "dir", "mode": mode,
                        "mtime": int(member.mtime),
                    })
                continue
            if target.is_dir() and not target.is_symlink():
                raise GarbError(f"archive file conflicts with an existing directory: {rel}")
            if target.exists() or target.is_symlink():
                target.unlink()
            if member.issym():
                safe_symlink_target(member.linkname, str(PurePosixPath(rel).parent))
                os.symlink(member.linkname, target)
                if manifest:
                    entries.append({
                        "path": rel, "type": "symlink", "target": member.linkname,
                        "mode": mode, "mtime": int(member.mtime),
                    })
                continue
            handle = tar.extractfile(member)
            if handle is None:
                raise GarbError(f"cannot read archive member: {rel}")
            digest = hashlib.sha256()
            with open(target, "wb") as output:
                while True:
                    chunk = handle.read(65536)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output.write(chunk)
            os.chmod(target, mode)
            if manifest:
                entries.append({
                    "path": rel, "type": "file", "mode": mode,
                    "mtime": int(member.mtime), "sha256": digest.hexdigest(),
                })
    if manifest:
        entries.sort(key=lambda entry: entry["path"])
    return entries


def write_canonical_archive(entries: list[dict], source: Path, dest: Path, mtime: int) -> None:
    """Write a package archive in the same deterministic format as build_package()."""
    if not isinstance(mtime, int) or isinstance(mtime, bool) or mtime < 0:
        raise GarbError("invalid archive timestamp")
    ordered = sorted(entries, key=lambda entry: (entry["path"] != METADATA_NAME, entry["path"]))
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for entry in ordered:
                info = tarfile.TarInfo(entry["path"])
                info.mtime = mtime
                info.mode = int(entry.get("mode", 0o644)) & 0o7777
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                kind = entry.get("type")
                if kind == "dir":
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = safe_symlink_target(
                        str(entry.get("target", "")),
                        str(PurePosixPath(entry["path"]).parent),
                    )
                    tar.addfile(info)
                elif kind == "file":
                    payload = source / entry["path"]
                    if not payload.is_file() or payload.is_symlink():
                        raise GarbError(f"missing archive payload: {entry['path']}")
                    expected = entry.get("sha256")
                    if not isinstance(expected, str) or not SHA256_RE.match(expected):
                        raise GarbError(f"invalid payload hash for {entry['path']}")
                    if sha256_file(payload) != expected:
                        raise GarbError(f"payload hash mismatch: {entry['path']}")
                    info.type = tarfile.REGTYPE
                    info.size = payload.stat().st_size
                    with open(payload, "rb") as handle:
                        tar.addfile(info, handle)
                else:
                    raise GarbError(f"unsupported archive tree entry: {entry['path']}")
    dest.write_bytes(raw.getvalue())


def validate_delta_tree(tree: object) -> list[dict]:
    if not isinstance(tree, list) or not tree:
        raise GarbError("delta metadata has no tree")
    seen: set[str] = set()
    entries: list[dict] = []
    for raw in tree:
        if not isinstance(raw, dict):
            raise GarbError("delta tree entry is not an object")
        rel = normalise_member(str(raw.get("path", "")))
        if rel in seen:
            raise GarbError(f"duplicate path in delta tree: {rel}")
        seen.add(rel)
        kind = raw.get("type")
        entry = {
            "path": rel,
            "type": kind,
            "mode": parse_mode(raw.get("mode"), 0o644),
            "mtime": raw.get("mtime"),
        }
        if kind == "dir":
            pass
        elif kind == "symlink":
            target = raw.get("target")
            if not isinstance(target, str):
                raise GarbError(f"delta symlink has no target: {rel}")
            safe_symlink_target(target, str(PurePosixPath(rel).parent))
            entry["target"] = target
        elif kind == "file":
            digest = raw.get("sha256")
            if not isinstance(digest, str) or not SHA256_RE.match(digest):
                raise GarbError(f"delta file has no valid hash: {rel}")
            entry["sha256"] = digest
        else:
            raise GarbError(f"unsupported delta tree entry type: {rel}")
        entries.append(entry)
    return entries
