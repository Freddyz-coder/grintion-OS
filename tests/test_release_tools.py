from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GARB = REPO_ROOT / "bin" / "garb"
VERIFY = REPO_ROOT / "bin" / "grintion-release-verify"
SECURITY = REPO_ROOT / "bin" / "grintion-security-report"
HWINFO = REPO_ROOT / "bin" / "grintion-hwinfo"
DOCTOR = REPO_ROOT / "bin" / "grintion-doctor"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def write_checksum(artifact: Path, sums: Path) -> None:
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    sums.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")


def make_keys(tmp_path: Path) -> Path:
    keys = tmp_path / "keys"
    subprocess.run(
        [sys.executable, str(GARB), "keygen", str(keys)],
        check=True,
        capture_output=True,
    )
    return keys


def sign_checksum(sums: Path, private_key: Path) -> None:
    subprocess.run(
        [
            "openssl", "pkeyutl", "-sign", "-inkey", str(private_key),
            "-rawin", "-in", str(sums), "-out", str(sums) + ".sig",
        ],
        check=True,
        capture_output=True,
    )


def test_release_verify_accepts_checksum_and_signature(tmp_path: Path) -> None:
    artifact = tmp_path / "grintion-os-x86_64.iso"
    artifact.write_bytes(b"release artifact\n")
    sums = tmp_path / "SHA256SUMS"
    write_checksum(artifact, sums)
    keys = make_keys(tmp_path)
    sign_checksum(sums, keys / "private.pem")

    result = run(
        VERIFY,
        str(artifact),
        "--sha256-file", str(sums),
        "--key", str(keys / "public.pem"),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["checksum_ok"] is True
    assert payload["signature"] == "verified"
    assert payload["ok"] is True


def test_release_verify_rejects_a_modified_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "grintion-os-x86_64.iso"
    artifact.write_bytes(b"release artifact\n")
    sums = tmp_path / "SHA256SUMS"
    write_checksum(artifact, sums)
    artifact.write_bytes(b"tampered\n")

    result = run(VERIFY, str(artifact), "--sha256-file", str(sums))
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr


def test_release_verify_can_require_a_signature(tmp_path: Path) -> None:
    artifact = tmp_path / "grintion-os-x86_64.iso"
    artifact.write_bytes(b"release artifact\n")
    sums = tmp_path / "SHA256SUMS"
    write_checksum(artifact, sums)

    result = run(
        VERIFY, str(artifact),
        "--sha256-file", str(sums),
        "--require-signature",
    )
    assert result.returncode != 0
    assert "require-signature" in result.stderr.lower()


def test_security_report_json_contract() -> None:
    result = run(SECURITY, "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == 1
    assert set(payload["summary"]) == {"ok", "warn", "fail", "info"}
    identifiers = {check["id"] for check in payload["checks"]}
    assert {"secure-boot", "firewall", "listeners", "sysctls"} <= identifiers
    assert all(check["status"] in {"ok", "warn", "fail", "info"}
               for check in payload["checks"])


def test_doctor_delegates_security_report() -> None:
    result = subprocess.run(
        ["sh", str(DOCTOR), "--security", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == 1
    assert "checks" in payload


def test_hwinfo_json_is_redacted_by_default() -> None:
    result = run(HWINFO, "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == 1
    assert payload["redacted"] is True
    for key in ("kernel", "cpu", "memory", "pci", "usb", "network", "storage", "firmware"):
        assert key in payload
    included = run(HWINFO, "--json", "--include-identifiers")
    assert included.returncode == 0, included.stderr
    assert json.loads(included.stdout)["redacted"] is False
