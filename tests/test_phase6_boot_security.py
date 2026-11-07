from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SECUREBOOT = REPO_ROOT / "bin" / "grintion-secureboot"
UKI = REPO_ROOT / "bin" / "grintion-uki"
ATTEST = REPO_ROOT / "bin" / "grintion-attest"
TPM_LUKS = REPO_ROOT / "bin" / "grintion-tpm-luks"
FIRMWARE = REPO_ROOT / "bin" / "grintion-firmware"
HIBERNATE = REPO_ROOT / "bin" / "grintion-hibernate"
KERNEL = REPO_ROOT / "bin" / "grintion-kernel"
MODULE_SIGN = REPO_ROOT / "bin" / "grintion-module-sign"


def test_secureboot_key_generation_and_signing(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    # Generate keys
    r1 = subprocess.run([str(SECUREBOOT), "generate-keys", "--dir", str(keys_dir)], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    key_file = keys_dir / "MOK.key"
    cert_file = keys_dir / "MOK.crt"
    der_file = keys_dir / "MOK.der"
    assert key_file.is_file()
    assert cert_file.is_file()
    assert der_file.is_file()

    # Create dummy binary
    dummy_bin = tmp_path / "test.efi"
    dummy_bin.write_bytes(b"MZ_DUMMY_EFI_EXECUTABLE_CODE")
    signed_bin = tmp_path / "signed.efi"

    # Sign binary
    r2 = subprocess.run([
        str(SECUREBOOT), "sign",
        "--key", str(key_file), "--cert", str(cert_file),
        "--in", str(dummy_bin), "--out", str(signed_bin)
    ], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert signed_bin.is_file()

    # Verify signature
    r3 = subprocess.run([str(SECUREBOOT), "verify", "--cert", str(cert_file), "--in", str(signed_bin)], capture_output=True, text=True, check=False)
    assert r3.returncode == 0
    assert "PASSED" in r3.stdout

    # Stage MOK enrollment
    esp_dir = tmp_path / "esp"
    r4 = subprocess.run([str(SECUREBOOT), "enroll-mok", "--cert", str(der_file), "--esp", str(esp_dir)], capture_output=True, text=True, check=False)
    assert r4.returncode == 0
    assert (esp_dir / "EFI" / "grintion" / "MOK.der").is_file()


def test_uki_build_and_inspect(tmp_path: Path) -> None:
    kernel = tmp_path / "vmlinuz"
    kernel.write_bytes(b"LINUX_KERNEL_IMAGE_BYTES_6.12")
    initrd = tmp_path / "initramfs.img"
    initrd.write_bytes(b"INITRAMFS_CPIO_ARCHIVE_DATA")
    output_uki = tmp_path / "grintion.efi"

    # Build UKI
    r1 = subprocess.run([
        str(UKI), "build",
        "--kernel", str(kernel),
        "--initrd", str(initrd),
        "--cmdline", "root=LABEL=GRINTION rw console=ttyS0",
        "--output", str(output_uki)
    ], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    assert output_uki.is_file()

    # Inspect UKI
    r2 = subprocess.run([str(UKI), "inspect", str(output_uki), "--json"], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    info = json.loads(r2.stdout)
    assert info["type"] == "Unified Kernel Image (PE/COFF)"
    assert "root=LABEL=GRINTION" in info["cmdline"]
    assert ".linux" in info["sections"]
    assert ".initrd" in info["sections"]


def test_tpm_attestation_and_baseline_verification(tmp_path: Path) -> None:
    baseline_file = tmp_path / "pcr-baseline.json"

    # Snapshot current PCRs
    r1 = subprocess.run([str(ATTEST), "snapshot", "--output", str(baseline_file)], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    assert baseline_file.is_file()

    # Verify matching baseline
    r2 = subprocess.run([str(ATTEST), "verify", "--baseline", str(baseline_file), "--json"], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    data2 = json.loads(r2.stdout)
    assert data2["success"] is True

    # Alter simulated PCR 4 (bootloader) to test tampering detection
    env = os.environ.copy()
    tampered_pcrs = {
        "0": "0000000000000000000000000000000000000000000000000000000000000000",
        "4": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "7": "1111111111111111111111111111111111111111111111111111111111111111",
    }
    env["GRINTION_PCR_MOCK"] = json.dumps(tampered_pcrs)
    r3 = subprocess.run([str(ATTEST), "verify", "--baseline", str(baseline_file), "--json"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 1
    data3 = json.loads(r3.stdout)
    assert data3["success"] is False
    assert "4" in data3["deviations"]


def test_tpm_luks_seal_and_fallback(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # Seal LUKS device
    r1 = subprocess.run([str(TPM_LUKS), "seal", "--device", "/dev/vda2", "--pcrs", "0,7"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0

    # Status check
    r2 = subprocess.run([str(TPM_LUKS), "status", "--device", "/dev/vda2", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    stat = json.loads(r2.stdout)
    assert stat["tpm_sealed"] is True
    assert stat["pcr_match"] is True

    # Unseal when PCRs match
    r3 = subprocess.run([str(TPM_LUKS), "unseal", "--device", "/dev/vda2"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    assert "TPM 2.0 unseal successful" in r3.stdout

    # Tamper PCRs and test fallback
    env["GRINTION_PCR_MOCK"] = json.dumps({"0": "altered_pcr_val", "7": "altered_pcr_val"})
    r4 = subprocess.run([str(TPM_LUKS), "unseal", "--device", "/dev/vda2"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 1
    assert "falling back to interactive passphrase prompt" in r4.stderr


def test_firmware_esrt_and_capsule(tmp_path: Path) -> None:
    # Status
    r1 = subprocess.run([str(FIRMWARE), "status", "--json"], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    entries = json.loads(r1.stdout)
    assert len(entries) >= 1

    # Stage capsule
    capsule = tmp_path / "system_firmware.cap"
    capsule.write_bytes(b"EFI_CAPSULE_HEADER_MAGIC_PAYLOAD_DATA_BYTES")
    esp = tmp_path / "esp"

    r2 = subprocess.run([str(FIRMWARE), "apply-capsule", str(capsule), "--esp", str(esp)], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert (esp / "EFI" / "UpdateCapsule" / "system_firmware.cap").is_file()


def test_hibernation_preflight_and_setup(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)
    env["GRINTION_MOCK_RAM_KIB"] = str(4 * 1024 * 1024)  # 4 GiB
    env["GRINTION_MOCK_SWAPS"] = json.dumps([
        {"path": "/dev/vda3", "type": "partition", "size_kib": 8 * 1024 * 1024, "used_kib": 0}
    ])
    env["GRINTION_MOCK_CMDLINE"] = "BOOT_IMAGE=/boot/vmlinuz root=/dev/vda2 rw resume=UUID=1234"

    # Preflight check
    r1 = subprocess.run([str(HIBERNATE), "check", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    data = json.loads(r1.stdout)
    assert data["status"] == "ready"
    assert data["swap_total_mib"] == 8192

    # Setup
    env["GRINTION_MOCK_SWAP_UUID"] = "11223344-5566-7788-99aa-bbccddeeff00"
    r2 = subprocess.run([str(HIBERNATE), "setup", "--swap", "/dev/vda3", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    conf = (tmp_path / "etc" / "grintion" / "resume.conf").read_text()
    assert "RESUME_UUID=11223344-5566-7788-99aa-bbccddeeff00" in conf


def test_kernel_manager_and_module_signing(tmp_path: Path) -> None:
    boot = tmp_path / "boot"
    boot.mkdir()
    (boot / "vmlinuz-6.12-grintion").write_bytes(b"KERNEL1")
    (boot / "initramfs-6.12-grintion.img").write_bytes(b"INIT1")
    (boot / "vmlinuz-6.6-lts").write_bytes(b"KERNEL2")
    (boot / "initramfs-6.6-lts.img").write_bytes(b"INIT2")
    (boot / "limine.conf").write_text("timeout: 3\ndefault_entry: 1\n")

    # List kernels
    r1 = subprocess.run([str(KERNEL), "list", "--boot", str(boot), "--json"], capture_output=True, text=True, check=False)
    assert r1.returncode == 0
    kernels = json.loads(r1.stdout)
    assert len(kernels) == 2
    assert kernels[0]["is_default"] is True

    # Set default kernel
    r2 = subprocess.run([str(KERNEL), "set-default", "2", "--boot", str(boot)], capture_output=True, text=True, check=False)
    assert r2.returncode == 0
    assert "default_entry: 2" in (boot / "limine.conf").read_text()

    # Module signing
    key = tmp_path / "mod.key"
    cert = tmp_path / "mod.crt"
    key.write_text("KEY")
    cert.write_text("CERT")
    mod = tmp_path / "driver.ko"
    mod.write_bytes(b"ELF_KERNEL_MODULE_CODE")

    r3 = subprocess.run([str(MODULE_SIGN), "sign", "--key", str(key), "--cert", str(cert), str(mod)], capture_output=True, text=True, check=False)
    assert r3.returncode == 0

    r4 = subprocess.run([str(MODULE_SIGN), "verify", str(mod)], capture_output=True, text=True, check=False)
    assert r4.returncode == 0

