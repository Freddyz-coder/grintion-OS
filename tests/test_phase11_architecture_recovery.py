from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"


def run_bin(name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        [str(BIN_DIR / name), *args], capture_output=True, text=True, env=environ, check=False
    )


def test_arch_reports_64_and_32_bit_compatibility(tmp_path: Path) -> None:
    libs = tmp_path / "lib32"
    libs.mkdir()
    (libs / "ld-linux.so.2").write_text("loader")
    env = {
        "GRINTION_CPU_BITS": "64",
        "GRINTION_MACHINE": "x86_64",
        "GRINTION_USERLAND_BITS": "64",
        "GRINTION_IA32_KERNEL": "1",
        "GRINTION_IA32_LIBS": str(libs),
    }
    status = run_bin("grintion-arch", "status", "--json", env=env)
    assert status.returncode == 0, status.stderr
    data = json.loads(status.stdout)
    assert data["can_run_64"] is True
    assert data["can_run_32"] is True
    assert "32-bit compatibility" in data["policy"]
    assert run_bin("grintion-arch", "check", "--require", "32", env=env).returncode == 0


def test_arch_refuses_install_on_a_32_bit_only_cpu(tmp_path: Path) -> None:
    env = {
        "GRINTION_CPU_BITS": "32",
        "GRINTION_MACHINE": "i686",
        "GRINTION_USERLAND_BITS": "32",
        "GRINTION_IA32_KERNEL": "0",
        "GRINTION_IA32_LIBS": str(tmp_path / "missing"),
    }
    status = run_bin("grintion-arch", "status", "--json", env=env)
    data = json.loads(status.stdout)
    assert data["policy"] == "32-bit only"
    assert data["recommended_image"] == "i686"
    assert run_bin("grintion-arch", "check", "--require", "install", env=env).returncode == 1
    assert run_bin("grintion-arch", "check", "--require", "32", env=env).returncode == 0


def make_fake_hardware(tmp_path: Path) -> dict[str, str]:
    sysfs = tmp_path / "sys"
    device = sysfs / "bus/pci/devices/0000:03:00.0"
    device.mkdir(parents=True)
    (device / "class").write_text("0x028000\n")
    (device / "vendor").write_text("0x8086\n")
    (device / "device").write_text("0xa0f0\n")
    (device / "modalias").write_text(
        "pci:v00008086d0000A0F0sv00008086sd00000001bc02sc80i00\n"
    )

    modules = tmp_path / "modules"
    modules.mkdir()
    (modules / "modules.alias").write_text(
        "alias pci:v00008086d0000A0F0sv*sd*bc*sc*i* iwlwifi\n"
    )
    (modules / "modules.builtin").write_text("")

    modinfo = tmp_path / "modinfo"
    modinfo.write_text(
        "#!/bin/sh\n"
        '[ "$1" = "-F" ] && [ "$2" = "firmware" ] || exit 1\n'
        "printf '%s\\n' iwlwifi-cc-a0-77.ucode\n"
    )
    modinfo.chmod(0o755)
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    return {
        "GRINTION_SYSFS": str(sysfs),
        "GRINTION_MODULES_DIR": str(modules),
        "GRINTION_MODINFO": str(modinfo),
        "GRINTION_FIRMWARE_DIRS": str(firmware),
    }


def test_driver_select_names_the_missing_wifi_firmware(tmp_path: Path) -> None:
    env = make_fake_hardware(tmp_path)
    result = run_bin("grintion-driver-select", "--json", "--root", str(tmp_path), env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["base_image_has_firmware"] is True  # the empty test root exists
    assert data["missing_firmware_count"] == 1
    device = data["devices"][0]
    assert device["wireless"] is True
    assert device["modules"] == ["iwlwifi"]
    assert "linux-firmware-intel" in device["packages"]
    assert "will not work on the base image" in device["message"]
    assert (tmp_path / "etc/grintion/hardware-profile.json").is_file()
    assert (tmp_path / "etc/modules-load.d/grintion-hardware.conf").is_file()

    modules = run_bin(
        "grintion-driver-select", "--initramfs-modules", "--root", str(tmp_path), env=env
    )
    assert modules.returncode == 0
    assert "iwlwifi" in modules.stdout


def test_hwreport_explains_that_wifi_needs_firmware(tmp_path: Path) -> None:
    env = make_fake_hardware(tmp_path)
    result = run_bin("grintion-hwreport", "--json", env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    firmware = data["device_firmware"]
    assert firmware["missing_count"] == 1
    device = firmware["devices"][0]
    assert device["works_on_base"] is False
    assert "this Wi-Fi card needs" in device["message"]
    assert "will not work on the base image" in device["message"]
    assert "iwlwifi-cc-a0-77.ucode" in device["missing_firmware"]


def test_selfheal_repairs_staged_state(tmp_path: Path) -> None:
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp").chmod(0o755)
    (tmp_path / "var/service").mkdir(parents=True)
    (tmp_path / "var/service/dead").symlink_to(tmp_path / "missing")
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/resolv.conf").write_text("")

    env = {
        "GRINTION_ROOT": str(tmp_path),
        "GRINTION_SELFHEAL_STATE": str(tmp_path / "var/lib/grintion/selfheal"),
        "GRINTION_SELFHEAL_LOG": str(tmp_path / "var/log/grintion-selfheal.log"),
    }
    result = run_bin("grintion-selfheal", "run", "--json", env=env)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "tmp").stat().st_mode & 0o7777 == 0o1777
    assert not (tmp_path / "var/service/dead").is_symlink()
    assert "nameserver" in (tmp_path / "etc/resolv.conf").read_text()
    assert "repairs" in json.loads(result.stdout)
    assert (tmp_path / "var/log/grintion-selfheal.log").is_file()


def test_auditd_service_has_userspace_and_rules() -> None:
    required = (REPO_ROOT / "config/rootfs.audit-binaries").read_text()
    for binary in ("auditd", "auditctl", "ausearch", "aureport"):
        assert binary in required
    service = (REPO_ROOT / "etc/sv/auditd/run").read_text()
    assert "auditctl -R" in service
    assert "refusing to fake the service" in service
    assert "auditd -f" in service
    assert (REPO_ROOT / "etc/audit/auditd.conf").is_file()
    assert "-k identity" in (REPO_ROOT / "etc/audit/audit.rules").read_text()


def test_kernel_contract_covers_audit_ia32_and_zram() -> None:
    fragment = (REPO_ROOT / "config/kernel-hardened.config").read_text()
    for line in (
        "CONFIG_IA32_EMULATION=y",
        "CONFIG_AUDIT=y",
        "CONFIG_AUDITSYSCALL=y",
        "CONFIG_ZRAM=m",
        "CONFIG_ZRAM_BACKEND_ZSTD=y",
        "CONFIG_ZSMALLOC=m",
    ):
        assert line in fragment


def test_snapshot_rollback_and_prune_are_documented_in_help() -> None:
    result = run_bin("grintion-snapshot", "--help")
    assert result.returncode == 0
    assert "rollback NAME" in result.stdout
    assert "prune" in result.stdout
    assert "--dry-run" in result.stdout
