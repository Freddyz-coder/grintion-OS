from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GARB = REPO_ROOT / "bin" / "garb"


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(GARB), "--root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"garb {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    return result


def write_package(src: Path, name: str, version: str = "1.0.0", deps: list[str] | None = None,
                  files: dict[str, str] | None = None) -> None:
    pkg = src / name
    (pkg / "root" / "usr" / "share" / name).mkdir(parents=True, exist_ok=True)
    (pkg / "root" / "usr" / "share" / name / "data.txt").write_text(f"{name}-{version}\n")
    for rel, content in (files or {}).items():
        path = pkg / "root" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    manifest = [
        "[package]",
        f'name = "{name}"',
        f'version = "{version}"',
        "release = 1",
        f'description = "{name} test package"',
        'arch = ["x86_64"]',
    ]
    if deps:
        manifest += ["", "[dependencies]", f"runtime = {json.dumps(deps)}"]
    (pkg / "Garbfile").write_text("\n".join(manifest) + "\n")


@pytest.fixture()
def environment(tmp_path: Path) -> dict:
    src = tmp_path / "src"
    repo = tmp_path / "repo"
    keys = tmp_path / "keys"
    root = tmp_path / "root"
    src.mkdir()
    write_package(src, "libfoo")
    write_package(src, "app", deps=["libfoo"], files={"usr/bin/app": "app-ok\n"})
    (src / "app" / "root" / "usr" / "bin" / "app").chmod(0o755)
    subprocess.run([sys.executable, str(GARB), "keygen", str(keys)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
                   check=True, capture_output=True)
    (root / "etc/garb/repos.d").mkdir(parents=True)
    (root / "etc/garb/keys").mkdir(parents=True)
    (root / "etc/garb/repos.d/demo.conf").write_text(f"url={repo}\n")
    shutil.copy(keys / "public.pem", root / "etc/garb/keys/demo.pub")
    run(root, "update")
    return {"src": src, "repo": repo, "keys": keys, "root": root}


def test_signed_install_dependencies_and_remove(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    assert (root / "usr/bin/app").read_text() == "app-ok\n"
    assert (root / "usr/share/libfoo/data.txt").read_text() == "libfoo-1.0.0\n"
    run(root, "verify")
    run(root, "remove", "app", "libfoo")
    assert not (root / "usr/bin/app").exists()
    assert not (root / "usr/share/libfoo/data.txt").exists()


def test_tamper_is_detected(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    (root / "usr/bin/app").write_text("evil\n")
    result = run(root, "verify", check=False)
    assert result.returncode != 0
    assert "TAMPERED" in result.stdout


def test_bad_signature_fails_closed(environment: dict) -> None:
    root = environment["root"]
    repo = environment["repo"]
    keys = environment["keys"]
    other = keys / "other"
    subprocess.run([sys.executable, str(GARB), "keygen", str(other)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "sign-index", str(repo / "index.json"),
                    "--key", str(other / "private.pem")], check=True, capture_output=True)
    result = run(root, "update", check=False)
    assert result.returncode != 0
    assert "signature" in result.stderr.lower()


def test_traversal_archive_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    evil = tmp_path / "pkg.garb"
    metadata = {
        "schema": 1,
        "name": "evil",
        "version": "1.0.0",
        "release": 1,
        "files": [{"path": "../escaped", "type": "file", "sha256": "0" * 64}],
    }
    with tarfile.open(evil, "w:gz") as tar:
        payload = json.dumps(metadata).encode()
        info = tarfile.TarInfo("GARB_METADATA.json")
        info.size = len(payload)
        import io
        tar.addfile(info, io.BytesIO(payload))
        data = b"owned\n"
        info = tarfile.TarInfo("../escaped")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    result = run(root, "install", str(evil), check=False)
    assert result.returncode != 0
    assert not (tmp_path / "escaped").exists()


def test_archive_checksum_mismatch_fails(environment: dict) -> None:
    root = environment["root"]
    repo = environment["repo"]
    archives = list(repo.glob("*.garb"))
    target = next(path for path in archives if path.name.startswith("app-"))
    with open(target, "ab") as handle:
        handle.write(b"tamper")
    result = run(root, "install", "app", check=False)
    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()


def test_upgrade(environment: dict) -> None:
    root = environment["root"]
    src = environment["src"]
    repo = environment["repo"]
    keys = environment["keys"]
    run(root, "install", "app")
    write_package(src, "app", version="2.0.0", deps=["libfoo"], files={"usr/bin/app": "app-v2\n"})
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
                   check=True, capture_output=True)
    run(root, "update")
    run(root, "upgrade")
    assert (root / "usr/bin/app").read_text() == "app-v2\n"
    entry = json.loads((root / "var/lib/garb/db.json").read_text())["packages"]["app"]
    assert entry["version"] == "2.0.0"
