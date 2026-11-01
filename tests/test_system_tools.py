from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHUTDOWN = REPO_ROOT / "bin" / "shutdown"
LIMINE = REPO_ROOT / "bin" / "limine-deploy"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_shutdown_dry_run_actions() -> None:
    assert "poweroff" in run(SHUTDOWN, "--dry-run", "-h").stdout
    assert "poweroff" in run(SHUTDOWN, "--dry-run", "-P").stdout
    assert "reboot" in run(SHUTDOWN, "--dry-run", "-r").stdout
    assert "halt" in run(SHUTDOWN, "--dry-run", "-H").stdout
    delayed = run(SHUTDOWN, "--dry-run", "-h", "+5")
    assert delayed.returncode == 0, delayed.stderr
    assert "300" in delayed.stdout


def test_shutdown_cancel_does_not_power_off() -> None:
    result = run(SHUTDOWN, "--dry-run", "-c")
    assert result.returncode == 0, result.stderr
    assert "cancel" in result.stdout
    assert "poweroff" not in result.stdout


def test_shutdown_rejects_unknown_option() -> None:
    result = run(SHUTDOWN, "--dry-run", "-Z")
    assert result.returncode != 0
    assert "unknown option" in result.stderr


def test_limine_deploy_installs_referenced_files(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("limine-bios.sys", "BOOTX64.EFI", "BOOTAA64.EFI"):
        (assets / name).write_bytes(b"asset")
    esp = tmp_path / "esp"
    esp.mkdir()
    kernel = tmp_path / "vmlinuz-grintion"
    kernel.write_bytes(b"kernel")
    initramfs = tmp_path / "initramfs-install.img"
    initramfs.write_bytes(b"initramfs")

    result = run(
        LIMINE,
        "--efi", str(esp),
        "--root-uuid", "abc-123",
        "--asset-dir", str(assets),
        "--kernel", str(kernel),
        "--initramfs", str(initramfs),
    )
    assert result.returncode == 0, result.stderr
    assert (esp / "EFI/grintion/vmlinuz-grintion").read_bytes() == b"kernel"
    assert (esp / "EFI/grintion/initramfs-install.img").read_bytes() == b"initramfs"
    assert (esp / "limine-bios.sys").exists()
    assert (esp / "EFI/BOOT/BOOTX64.EFI").exists()
    conf = (esp / "limine.conf").read_text()
    assert "root=UUID=abc-123" in conf
    assert "EFI/grintion/vmlinuz-grintion" in conf


def test_limine_deploy_refuses_missing_kernel(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("limine-bios.sys", "BOOTX64.EFI", "BOOTAA64.EFI"):
        (assets / name).write_bytes(b"asset")
    esp = tmp_path / "esp"
    esp.mkdir()
    initramfs = tmp_path / "initramfs-install.img"
    initramfs.write_bytes(b"initramfs")

    result = run(
        LIMINE,
        "--efi", str(esp),
        "--root-uuid", "abc-123",
        "--asset-dir", str(assets),
        "--kernel", str(tmp_path / "missing-kernel"),
        "--initramfs", str(initramfs),
    )
    assert result.returncode != 0
    assert "kernel not found" in result.stderr
    assert not (esp / "limine.conf").exists()
