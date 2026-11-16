from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOADER = importlib.machinery.SourceFileLoader(
    "release_audit", str(REPO_ROOT / "bin" / "release-audit")
)
SPEC = importlib.util.spec_from_loader("release_audit", LOADER)
assert SPEC is not None
release_audit = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(release_audit)


def test_semver_check() -> None:
    assert release_audit.is_semver("0.19.0")
    assert release_audit.is_semver("1.2.3-rc1")
    assert not release_audit.is_semver("0.19")
    assert not release_audit.is_semver("v0.19.0")
    assert not release_audit.is_semver("")


def test_limine_entry_parser_extracts_cmdlines() -> None:
    text = """/Grintion-OS 0.19.0 (live, RAM)
    cmdline: security=apparmor apparmor=1 audit=1 rd.shell=0 lockdown=confidentiality
/Grintion-OS 0.19.0 (recovery shell)
    cmdline: audit=1 lockdown=confidentiality
"""
    entries = release_audit.parse_limine_entries(text)
    assert len(entries) == 2
    assert "live" in entries[0]["name"]
    assert "rd.shell=0" in entries[0]["cmdline"]
    assert "recovery" in entries[1]["name"]


def test_cpio_setuid_parser() -> None:
    entries = [
        ("-rwsr-xr-x", "usr/bin/mount"),
        ("-rwxr-xr-x", "usr/bin/chroot"),
        ("-rwsr-sr-x", "usr/bin/extra"),
    ]
    assert release_audit.setuid_paths(entries) == {"usr/bin/mount", "usr/bin/extra"}


def test_checksum_parser(tmp_path: Path) -> None:
    payload = b"release"
    digest = hashlib.sha256(payload).hexdigest()
    checksum = tmp_path / "artifact.sha256"
    checksum.write_text(f"{digest}  artifact.iso\n", encoding="utf-8")
    assert release_audit.expected_sha256(checksum) == digest
    checksum.write_text("not-a-checksum\n", encoding="utf-8")
    assert release_audit.expected_sha256(checksum) is None


def test_missing_iso_fails_closed(tmp_path: Path) -> None:
    report = release_audit.check_artifact(tmp_path / "missing.iso", None, None)
    assert report.summary()["fail"] >= 1


def test_setuid_allowlist_matches_live_contract() -> None:
    assert len(release_audit.ALLOWED_SETUID) == 12
    assert "usr/bin/mount" in release_audit.ALLOWED_SETUID
    assert "usr/bin/sudo" in release_audit.ALLOWED_SETUID
