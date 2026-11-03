from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHUTDOWN = REPO_ROOT / "bin" / "shutdown"
LIMINE = REPO_ROOT / "bin" / "limine-deploy"
INSTALLER = REPO_ROOT / "bin" / "grintion-install"


def load_seed_module():
    path = REPO_ROOT / "build" / "seed-pacman-db.py"
    spec = importlib.util.spec_from_file_location("seed_pacman_db", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_stage3_never_stops_a_getty() -> None:
    # runsv signals a service's whole process group, so stopping the getty that
    # owns the console killed the poweroff command and left the machine running.
    stage3 = (REPO_ROOT / "etc" / "runit" / "3").read_text()
    assert "agetty-*" in stage3


def test_poweroff_requires_root_and_accepts_force() -> None:
    poweroff = REPO_ROOT / "bin" / "poweroff"
    result = run(poweroff, "-h")
    assert result.returncode == 0
    assert "-f" in result.stdout
    if os.geteuid() != 0:
        result = run(poweroff, "-f")
        assert result.returncode == 1
        assert "must be root" in result.stderr


def test_installer_help_lists_swap_size() -> None:
    result = subprocess.run(
        [str(INSTALLER), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--swap-size" in result.stdout


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


def test_seed_database_drops_packages_whose_libraries_are_absent(tmp_path: Path) -> None:
    # pacman never reinstalls a seeded dependency. glib2 was seeded without
    # libglib-2.0.so.0, so desktop scriptlets failed while pacman exited 0.
    seed = load_seed_module()
    root = tmp_path / "root"
    (root / "usr/lib").mkdir(parents=True)
    (root / "usr/lib/libpresent.so.1").write_bytes(b"lib")
    (root / "usr/bin").mkdir()
    (root / "usr/bin/binaryok").write_bytes(b"bin")

    def entry(name: str, files: list[str]) -> Path:
        path = tmp_path / "db" / f"{name}-1-1"
        path.mkdir(parents=True)
        (path / "desc").write_text(f"%NAME%\n{name}\n")
        (path / "files").write_text("%FILES%\n" + "\n".join(files) + "\n")
        return path

    present = entry("present", ["usr/", "usr/lib/", "usr/lib/libpresent.so.1"])
    ghost = entry("ghost", ["usr/", "usr/lib/", "usr/lib/libghost.so.1"])
    binary_ok = entry(
        "binaryok", ["usr/bin/binaryok", "usr/lib/libabsent.so.1"]
    )
    chosen, dropped = seed.installed_packages(
        {"present": present, "ghost": ghost, "binaryok": binary_ok}, root
    )
    assert set(chosen) == {"present", "binaryok"}
    assert dropped == ["ghost"]


def test_rootfs_seeds_pacman_after_library_resolution() -> None:
    # The seed checks that a package's libraries exist in the image. Running it
    # before resolve-libs.py marked every dependency library package absent.
    script = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert script.index("resolve-libs.py") < script.index("seed-pacman-db.py")


def test_profile_defines_append_path_for_package_snippets(tmp_path: Path) -> None:
    # Packages install /etc/profile.d snippets (perl, jre, flatpak) that call
    # Arch's append_path helper. Without it, every login shell after a desktop
    # install reported "append_path: command not found".
    profile = (REPO_ROOT / "etc" / "profile").read_text()
    snippets = tmp_path / "profile.d"
    snippets.mkdir()
    (snippets / "perlbin.sh").write_text("append_path /opt/test/bin\n")
    rendered = profile.replace("/etc/profile.d", str(snippets))
    rendered = rendered.replace("/etc/grintion/live", str(tmp_path / "not-live"))
    path = tmp_path / "profile"
    path.write_text(rendered)

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", '. "$1"; printf "%s" "$PATH"',
         "bash", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "append_path: command not found" not in result.stderr
    assert "/opt/test/bin" in result.stdout


def test_dbus_service_logs_off_the_console() -> None:
    # The service used to write console spam straight onto the login prompt.
    script = (REPO_ROOT / "etc" / "sv" / "dbus" / "run").read_text()
    assert "/var/log/dbus.log" in script
    assert script.index("/var/log/dbus.log") < script.index("dbus-daemon --system")


def test_desktop_install_streams_output_and_provisions_accounts() -> None:
    script = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    # Streaming output replaced an all-at-once $(...) capture that hid a
    # 7-10 minute download behind a blank screen.
    assert "tee -a" in script
    assert "provision_dbus_accounts" in script
    assert 'getent group "$group"' in script


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


def test_pacman_requires_database_signatures() -> None:
    conf = (REPO_ROOT / "etc" / "pacman.conf").read_text()
    assert "SigLevel = Required DatabaseRequired" in conf
    assert "LocalFileSigLevel = Required" in conf
    assert "DatabaseOptional" not in conf


def test_installer_never_accepts_password_argv() -> None:
    result = subprocess.run(
        [str(INSTALLER), "--password", "secret"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "visible in 'ps'" in result.stderr

    help_text = subprocess.run(
        [str(INSTALLER), "--help"], capture_output=True, text=True, check=False
    ).stdout
    assert "--password-stdin" in help_text
    assert "--password PASS" not in help_text


def test_pam_faillock_wheel_and_yescrypt_are_wired() -> None:
    modules = (REPO_ROOT / "config" / "rootfs.pam-modules").read_text()
    assert "pam_faillock.so" in modules
    assert "pam_wheel.so" in modules

    auth = (REPO_ROOT / "etc" / "pam.d" / "system-auth").read_text()
    assert "pam_faillock.so preauth" in auth
    assert "pam_faillock.so authfail" in auth
    assert "sha512" not in auth

    assert "pam_wheel.so" in (REPO_ROOT / "etc" / "pam.d" / "su").read_text()
    assert "ENCRYPT_METHOD  YESCRYPT" in (REPO_ROOT / "etc" / "login.defs").read_text()

    stage1 = (REPO_ROOT / "etc" / "runit" / "1").read_text()
    assert "/run/faillock" in stage1


def test_tmp_mounts_are_noexec_and_persistence_is_nosuid() -> None:
    stage1 = (REPO_ROOT / "etc" / "runit" / "1").read_text()
    assert "mode=1777,nosuid,nodev,noexec tmpfs /tmp" in stage1
    assert "mode=1777,nosuid,nodev,noexec tmpfs /var/tmp" in stage1
    live_init = (REPO_ROOT / "init" / "live-init").read_text()
    assert "noatime,nosuid,nodev" in live_init
    assert "noexec" in live_init


def test_kernel_contract_covers_framebuffer_and_module_signing() -> None:
    fragment = (REPO_ROOT / "config" / "kernel-hardened.config").read_text()
    for line in (
        "CONFIG_DRM_FBDEV_EMULATION=y",
        "CONFIG_MODULE_SIG=y",
        "CONFIG_MODULE_SIG_ALL=y",
        "CONFIG_MODULE_SIG_FORCE=y",
        "CONFIG_BINFMT_MISC=n",
    ):
        assert line in fragment

    # io_uring cannot be compiled out without CONFIG_EXPERT, which selects
    # CONFIG_DEBUG_KERNEL; it is disabled at runtime instead.
    sysctl = (REPO_ROOT / "etc" / "sysctl.d" / "99-grintion.conf").read_text()
    assert "kernel.io_uring_disabled = 2" in sysctl
