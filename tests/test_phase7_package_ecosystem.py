from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GARB = REPO_ROOT / "bin" / "garb"
AUDIT = REPO_ROOT / "bin" / "grintion-audit"
CHANNEL = REPO_ROOT / "bin" / "grintion-channel"
CHANGELOG = REPO_ROOT / "build" / "gen-changelog.py"


def test_garb_generations_and_rollback(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo = tmp_path / "repo"
    root.mkdir()
    repo.mkdir()

    # Build PkgA
    p1 = tmp_path / "pkgA"
    (p1 / "root" / "usr" / "bin").mkdir(parents=True)
    (p1 / "Garbfile").write_text('[package]\nname = "pkgA"\nversion = "1.0"\nrelease = 1\n')
    (p1 / "root" / "usr" / "bin" / "a").write_text("#!/bin/sh\necho A\n")
    (p1 / "root" / "usr" / "bin" / "a").chmod(0o755)
    subprocess.run([str(GARB), "build", str(p1 / "Garbfile"), "-o", str(repo)], check=True)

    # Build PkgB
    p2 = tmp_path / "pkgB"
    (p2 / "root" / "usr" / "bin").mkdir(parents=True)
    (p2 / "Garbfile").write_text('[package]\nname = "pkgB"\nversion = "1.0"\nrelease = 1\n')
    (p2 / "root" / "usr" / "bin" / "b").write_text("#!/bin/sh\necho B\n")
    (p2 / "root" / "usr" / "bin" / "b").chmod(0o755)
    subprocess.run([str(GARB), "build", str(p2 / "Garbfile"), "-o", str(repo)], check=True)

    # Install PkgA -> Generation 1
    r1 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "install", str(repo / "pkgA-1.0-1.garb")], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    assert (root / "usr" / "bin" / "a").is_file()

    # Install PkgB -> Generation 2
    r2 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "install", str(repo / "pkgB-1.0-1.garb")], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert (root / "usr" / "bin" / "b").is_file()

    # Query generations --format json
    r3 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "generations", "--format", "json"], capture_output=True, text=True, check=False)
    assert r3.returncode == 0
    gens = json.loads(r3.stdout)
    assert len(gens) >= 2
    assert gens[0]["id"] == 1
    assert gens[1]["id"] == 2

    # Roll back to Generation 1 (pkgB should be removed)
    r4 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "rollback-generation", "1"], capture_output=True, text=True, check=False)
    assert r4.returncode == 0
    assert (root / "usr" / "bin" / "a").is_file()
    assert not (root / "usr" / "bin" / "b").exists()

    # Database only lists pkgA
    db_data = json.loads((root / "var" / "lib" / "garb" / "db.json").read_text())
    assert "pkgA" in db_data["packages"]
    assert "pkgB" not in db_data["packages"]


def test_garb_hold_and_pin(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    # Hold package
    r1 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "hold", "kernel", "openssl"], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    holds_file = root / "etc" / "garb" / "holds.conf"
    assert holds_file.is_file()
    assert "kernel" in holds_file.read_text()
    assert "openssl" in holds_file.read_text()

    # Unhold package
    r2 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "unhold", "openssl"], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert "openssl" not in holds_file.read_text()
    assert "kernel" in holds_file.read_text()

    # Pin package
    r3 = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "pin", "openssl=3.0.12"], capture_output=True, text=True, check=False)
    assert r3.returncode == 0
    pins_file = root / "etc" / "garb" / "pins.conf"
    assert pins_file.is_file()
    assert "openssl = 3.0.12" in pins_file.read_text()


def test_garb_delta_create_and_apply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Old pkg v1
    p1 = tmp_path / "p1"
    (p1 / "root" / "usr" / "share").mkdir(parents=True)
    (p1 / "Garbfile").write_text('[package]\nname = "testpkg"\nversion = "1.0"\nrelease = 1\n')
    (p1 / "root" / "usr" / "share" / "data.txt").write_text("common data line\nold specific content\n")
    subprocess.run([str(GARB), "build", str(p1 / "Garbfile"), "-o", str(repo)], check=True)
    old_archive = repo / "testpkg-1.0-1.garb"

    # New pkg v2
    p2 = tmp_path / "p2"
    (p2 / "root" / "usr" / "share").mkdir(parents=True)
    (p2 / "Garbfile").write_text('[package]\nname = "testpkg"\nversion = "2.0"\nrelease = 1\n')
    (p2 / "root" / "usr" / "share" / "data.txt").write_text("common data line\nnew updated content\n")
    (p2 / "root" / "usr" / "share" / "extra.txt").write_text("added file\n")
    subprocess.run([str(GARB), "build", str(p2 / "Garbfile"), "-o", str(repo)], check=True)
    new_archive = repo / "testpkg-2.0-1.garb"

    delta_archive = tmp_path / "testpkg.garb-delta"
    reconstructed = tmp_path / "testpkg-reconstructed.garb"

    # delta-apply verifies the result against a signed index, not just the
    # delta's own metadata.
    keys = tmp_path / "keys"
    subprocess.run([str(GARB), "keygen", str(keys)], check=True, capture_output=True)
    subprocess.run(
        [str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
        check=True, capture_output=True,
    )

    # Create delta
    r1 = subprocess.run([
        str(GARB), "delta-create",
        "--old", str(old_archive),
        "--new", str(new_archive),
        "--out", str(delta_archive),
    ], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    assert delta_archive.is_file()

    # Apply delta
    r2 = subprocess.run([
        str(GARB), "delta-apply",
        "--old", str(old_archive),
        "--delta", str(delta_archive),
        "--out", str(reconstructed),
        "--index", str(repo / "index.json"),
        "--key", str(keys / "public.pem"),
        "--package", "testpkg",
    ], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert reconstructed.is_file()

    # Verify reconstructed archive extracts new files
    extract_test = tmp_path / "extract_test"
    extract_test.mkdir()
    subprocess.run(["tar", "-xzf", str(reconstructed), "-C", str(extract_test)], check=True)
    assert (extract_test / "usr" / "share" / "extra.txt").is_file()
    assert "new updated content" in (extract_test / "usr" / "share" / "data.txt").read_text()


def test_garb_delta_apply_rejects_traversal(tmp_path: Path) -> None:
    import io
    import tarfile

    source = tmp_path / "p1"
    (source / "root" / "usr" / "share").mkdir(parents=True)
    (source / "Garbfile").write_text(
        '[package]\nname = "testpkg"\nversion = "1.0"\nrelease = 1\n'
    )
    (source / "root" / "usr" / "share" / "data.txt").write_text("old\n")
    repo = tmp_path / "repo"
    subprocess.run([str(GARB), "build", str(source / "Garbfile"), "-o", str(repo)], check=True)
    old_archive = repo / "testpkg-1.0-1.garb"

    delta = tmp_path / "evil.garb-delta"
    meta = {
        "format": "garb-delta-v2",
        "package": "testpkg",
        "new_sha256": "0" * 64,
        "mtime": 0,
        "tree": [{
            "path": "../escape",
            "type": "file",
            "mode": 0o644,
            "sha256": "0" * 64,
        }],
        "modified": ["../escape"],
        "deleted": [],
    }
    payload = (json.dumps(meta) + "\n").encode("utf-8")
    with tarfile.open(delta, "w:gz") as tar:
        info = tarfile.TarInfo("GARB_DELTA_METADATA.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    output = tmp_path / "reconstructed.garb"
    result = subprocess.run([
        str(GARB), "delta-apply",
        "--old", str(old_archive),
        "--delta", str(delta),
        "--out", str(output),
        "--index", str(tmp_path / "missing-index.json"),
        "--key", str(tmp_path / "missing.pem"),
    ], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "parent traversal" in result.stderr
    assert not output.exists()
    assert not (tmp_path / "escape").exists()


def test_garb_version_constraints_and_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo = tmp_path / "repo"
    root.mkdir()
    repo.mkdir()

    # Base library v1.0
    lib1 = tmp_path / "libA1"
    (lib1 / "root" / "usr" / "lib").mkdir(parents=True)
    (lib1 / "Garbfile").write_text('[package]\nname = "libA"\nversion = "1.0"\nrelease = 1\n')
    (lib1 / "root" / "usr" / "lib" / "liba.so").write_text("SO1")
    subprocess.run([str(GARB), "build", str(lib1 / "Garbfile"), "-o", str(repo)], check=True)

    # Base library v2.0
    lib2 = tmp_path / "libA2"
    (lib2 / "root" / "usr" / "lib").mkdir(parents=True)
    (lib2 / "Garbfile").write_text('[package]\nname = "libA"\nversion = "2.0"\nrelease = 1\n')
    (lib2 / "root" / "usr" / "lib" / "liba.so").write_text("SO2")
    subprocess.run([str(GARB), "build", str(lib2 / "Garbfile"), "-o", str(repo)], check=True)

    # App requiring libA>=2.0
    app = tmp_path / "app"
    (app / "root" / "usr" / "bin").mkdir(parents=True)
    (app / "Garbfile").write_text('[package]\nname = "appX"\nversion = "1.0"\nrelease = 1\n[dependencies]\nruntime = ["libA>=2.0"]\n')
    (app / "root" / "usr" / "bin" / "appx").write_text("#!/bin/sh\n")
    (app / "root" / "usr" / "bin" / "appx").chmod(0o755)
    subprocess.run([str(GARB), "build", str(app / "Garbfile"), "-o", str(repo)], check=True)

    # Index repo with libA 1.0 only
    repo_old = tmp_path / "repo_old"
    repo_old.mkdir()
    (repo_old / "libA-1.0-1.garb").write_bytes((repo / "libA-1.0-1.garb").read_bytes())
    (repo_old / "appX-1.0-1.garb").write_bytes((repo / "appX-1.0-1.garb").read_bytes())
    subprocess.run([str(GARB), "repo-index", str(repo_old)], check=True)

    # Configure repo
    repos_d = root / "etc" / "garb" / "repos.d"
    repos_d.mkdir(parents=True)
    (repos_d / "test.conf").write_text(f'[repository test]\nurl = file://{repo_old}\ntrusted = true\n')

    subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "update", "--allow-unsigned"], check=True)

    # Installing appX when only libA 1.0 is available must fail constraint libA>=2.0
    res = subprocess.run([str(GARB), "--root", str(root), "--backend", "native", "install", "appX"], capture_output=True, text=True, check=False)
    assert res.returncode != 0
    assert "requires libA>=2.0" in res.stderr


def test_grintion_audit_sbom_and_scan(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # Setup mock garb database
    db_file = tmp_path / "var" / "lib" / "garb" / "db.json"
    db_file.parent.mkdir(parents=True)
    db_file.write_text(json.dumps({
        "schema": 1,
        "packages": {
            "openssl": {
                "version": "3.0.7",
                "release": 1,
                "description": "Secure Sockets Layer toolkit",
                "license": "Apache-2.0",
                "archive_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                "installed_at": 1730000000,
                "files": [{"path": "usr/bin/openssl", "type": "file", "sha256": "11223344"}],
            }
        }
    }))

    # SPDX SBOM
    r1 = subprocess.run([str(AUDIT), "sbom", "--format", "spdx"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    spdx = json.loads(r1.stdout)
    assert spdx["spdxVersion"] == "SPDX-2.3"
    assert any(p["name"] == "openssl" for p in spdx["packages"])

    # CycloneDX SBOM
    r2 = subprocess.run([str(AUDIT), "sbom", "--format", "cyclonedx"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    cdx = json.loads(r2.stdout)
    assert cdx["bomFormat"] == "CycloneDX"
    assert any(c["name"] == "openssl" for c in cdx["components"])

    # Provenance
    r3 = subprocess.run([str(AUDIT), "provenance", "openssl", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    prov = json.loads(r3.stdout)
    assert prov["package"] == "openssl"
    assert prov["signature_verified"] is True

    # Vulnerability scan against feed
    feed_file = tmp_path / "advisories.json"
    feed_file.write_text(json.dumps([
        {
            "id": "CVE-2026-9999",
            "package": "openssl",
            "affected": "<3.0.10",
            "fixed": "3.0.10",
            "severity": "HIGH",
            "title": "Buffer overflow in handshake parser",
        }
    ]))
    r4 = subprocess.run([str(AUDIT), "scan", "--feed", str(feed_file), "--json"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 1  # 1 because vulnerabilities found
    findings = json.loads(r4.stdout)
    assert len(findings) == 1
    assert findings[0]["cve_id"] == "CVE-2026-9999"
    assert findings[0]["package"] == "openssl"


def test_grintion_channel_management(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # Initial get
    r1 = subprocess.run([str(CHANNEL), "get", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    assert json.loads(r1.stdout)["channel"] == "stable"

    # Switch to beta
    r2 = subprocess.run([str(CHANNEL), "set", "beta"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    assert (tmp_path / "etc" / "grintion" / "channel").read_text().strip() == "beta"

    # Re-query
    r3 = subprocess.run([str(CHANNEL), "get", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    assert json.loads(r3.stdout)["channel"] == "beta"


def test_changelog_generator(tmp_path: Path) -> None:
    out = tmp_path / "CHANGELOG.md"
    r1 = subprocess.run([str(CHANGELOG), "--version", "0.10.0", "--output", str(out)], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    assert out.is_file()
    text = out.read_text()
    assert "## [0.10.0]" in text

