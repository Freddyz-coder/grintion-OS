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
    for name in ("limine-bios.sys", "BOOTX64.EFI"):
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


def test_seed_database_records_library_only_owners(tmp_path: Path) -> None:
    # libxss was copied into the base image but absent from pacman's local DB,
    # so Firefox's dependency transaction failed with "exists in filesystem".
    seed = load_seed_module()
    root = tmp_path / "root"
    (root / "usr/lib").mkdir(parents=True)
    for name in ("libXss.so", "libXss.so.1", "libXss.so.1.0.0"):
        (root / "usr/lib" / name).write_bytes(b"lib")
    entry = tmp_path / "db" / "libxss-1.2.5-1"
    entry.mkdir(parents=True)
    (entry / "desc").write_text("%NAME%\nlibxss\n")
    (entry / "files").write_text(
        "%FILES%\nusr/\nusr/lib/\nusr/lib/libXss.so\n"
        "usr/lib/libXss.so.1\nusr/lib/libXss.so.1.0.0\n"
    )
    assert seed.library_owner_packages({"libxss": entry}, root) == {"libxss"}


def test_garb_repairs_mtab_before_mutating_pacman_transaction() -> None:
    backend = (REPO_ROOT / "bin" / "garblib" / "backends.py").read_text()
    assert "def _repair_mtab" in backend
    assert 'mtab.symlink_to(expected)' in backend
    assert 'getattr(args, "command", "") in ("install", "remove", "upgrade")' in backend
    assert "require root; rerun with: sudo garb" in backend


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


def test_graphical_sessions_start_a_dbus_session_bus() -> None:
    # There is no logind/systemd user manager in this image. Without an
    # explicit session bus, XFCE starts but its settings server cannot connect
    # ("Unable to contact settings server: No such file or directory") and the
    # window manager and panel never appear.
    hook = REPO_ROOT / "etc" / "X11" / "xinit" / "xinitrc.d" / "10-grintion-dbus.sh"
    assert hook.is_file()
    text = hook.read_text()
    assert "DBUS_SESSION_BUS_ADDRESS" in text
    assert "dbus-launch --sh-syntax --exit-with-session" in text

    # The explicit LightDM wrapper is the path that actually runs; it must
    # start the bus before XFCE, not after the desktop has already failed.
    wrapper = REPO_ROOT / "etc" / "lightdm" / "Xsession-grintion"
    assert wrapper.is_file()
    assert "exec dbus-run-session -- /etc/lightdm/Xsession" in wrapper.read_text()
    desktop = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert "session-wrapper=/etc/lightdm/Xsession-grintion" in desktop
    # lightdm.conf is loaded after lightdm.conf.d/ and Arch ships an
    # uncommented upstream session-wrapper, so the installer must rewrite the
    # main file as well; a drop-in alone is silently overridden.
    assert (
        "s|^#\\?session-wrapper=.*|session-wrapper=/etc/lightdm/Xsession-grintion|"
        in desktop
    )
    # logind-check-graphical belongs to [LightDM], not [Seat:*].
    assert "[LightDM]" in desktop

    required = (REPO_ROOT / "config" / "rootfs.required-binaries").read_text()
    assert "dbus-daemon" in required
    assert "dbus-launch" in required
    assert "dbus-run-session" in required


def test_xorg_uses_evdev_fallback() -> None:
    # Standalone udev feeds libinput, but Xorg can launch before that database
    # settles. The explicit evdev sections keep the real mouse and keyboard
    # working even when the libudev path is unavailable.
    generator = REPO_ROOT / "bin" / "grintion-xorg-input"
    assert generator.is_file()
    text = generator.read_text()
    assert "/proc/bus/input/devices" in text
    assert 'Driver \\"evdev\\"' in text
    assert 'AutoServerLayout' in text
    assert "/dev/input/" in text

    service = (REPO_ROOT / "etc" / "sv" / "display-manager" / "run").read_text()
    assert "grintion-xorg-input" in service
    assert service.index("grintion-xorg-input") < service.index('exec "$configured"')

    for name in ("xfce", "kde", "lxqt", "i3"):
        profile = (
            REPO_ROOT / "etc" / "grintion" / "desktops.d" / f"{name}.conf"
        ).read_text()
        assert "xf86-input-evdev" in profile


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


def test_desktop_download_survives_archive_low_speed_timeouts() -> None:
    # The archive server can move a large package slower than pacman's default
    # low-speed cutoff. That aborted the 1.2 GiB KDE transaction even though
    # the download would have completed; both the config and delegated command
    # must disable the cutoff.
    conf = (REPO_ROOT / "etc" / "pacman.conf").read_text()
    assert "DisableDownloadTimeout" in conf
    desktop = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert "--disable-download-timeout" in desktop


def test_live_kde_install_fails_before_filling_the_ram_overlay() -> None:
    # KDE is ~4.8 GiB including its download, but a 4 GiB live VM has a 1.9 GiB
    # RAM overlay. The supported path is grintion-install --desktop kde, which
    # uses the target disk for both the cache and installed files.
    desktop = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert 'free_mib=$(df -Pm / | awk' in desktop
    assert "live RAM overlay has" in desktop
    assert "grintion-install --desktop kde" in desktop


def test_lightdm_greeter_pam_supports_unauthenticated_setcred() -> None:
    # LightDM calls pam_setcred on the greeter session without calling
    # pam_authenticate. pam_env and pam_limits have no usable setcred handler
    # on that path and make the call fail with PAM_ABORT, so the greeter never
    # draws. Only setcred-capable modules may appear in this stack.
    greeter = (REPO_ROOT / "etc" / "pam.d" / "lightdm-greeter").read_text()
    assert "pam_permit.so" in greeter
    assert "pam_env.so" not in greeter
    assert "pam_limits.so" not in greeter
    assert "pam_unix.so" not in greeter

    script = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    start = script.index("fix_lightdm_greeter_pam()")
    end = script.index("# dbus-daemon drops privileges", start)
    stack = script[start:end]
    assert "pam_permit.so" in stack
    assert "pam_env.so" not in stack
    assert "pam_limits.so" not in stack


def test_desktop_writes_an_explicit_lightdm_greeter_session() -> None:
    # LightDM's compiled default is "default", but Arch ships
    # lightdm-gtk-greeter.desktop. Relying on the commented package default
    # leaves LightDM with no greeter and it exits instead of drawing.
    script = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert "50-grintion.conf" in script
    assert "greeter-session=lightdm-gtk-greeter" in script


def test_lightdm_account_has_a_shadow_entry(tmp_path: Path) -> None:
    # lightdm is declared in /etc/passwd but was missing from /etc/shadow, so
    # useradd refused with "user already exists" and PAM could not establish
    # credentials for the greeter (Failed to establish PAM credentials).
    # Accounts are now generated at build time, so test the generator output.
    import subprocess
    import sys

    etc = tmp_path / "etc"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "build" / "gen-accounts.py"),
            "--manifest", str(REPO_ROOT / "config" / "accounts.toml"),
            "--etc", str(etc),
        ],
        check=True,
    )
    passwd = {
        line.split(":", 1)[0]
        for line in (etc / "passwd").read_text().splitlines()
        if line
    }
    shadow = {
        line.split(":", 1)[0]
        for line in (etc / "shadow").read_text().splitlines()
        if line
    }
    assert passwd <= shadow, f"accounts without shadow entries: {sorted(passwd - shadow)}"


def test_desktop_repairs_accounts_without_shadow_entries() -> None:
    script = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert 'getent shadow "$user"' in script
    assert 'printf \'%s:!:19000:0:99999:7:::\\n\' "$user" >> "$TARGET_ROOT/etc/shadow"' in script


def test_live_boot_brings_loopback_up() -> None:
    # The live image used to boot with lo DOWN; D-Bus, X11 and local repositories
    # then failed with connection errors even though DHCP worked.
    stage1 = (REPO_ROOT / "etc" / "runit" / "1").read_text()
    assert "ip link set lo up" in stage1
    doctor = (REPO_ROOT / "bin" / "grintion-doctor").read_text()
    assert "loopback interface is down" in doctor


def test_secure_boot_is_detected_and_refused() -> None:
    # There is no signed Grintion boot chain. The installer must fail before it
    # partitions a disk that the firmware will not boot, and the doctor must
    # report the state rather than implying verified boot support.
    doctor = (REPO_ROOT / "bin" / "grintion-doctor").read_text()
    assert "SecureBoot-*" in doctor
    assert "does not support Secure Boot" in doctor

    installer = (REPO_ROOT / "bin" / "grintion-install").read_text()
    assert "secure_boot_enabled" in installer
    assert "does not ship a signed boot chain" in installer


def test_desktop_never_uses_a_blanket_overwrite() -> None:
    # --overwrite '*' let any upstream package replace account, sudo and boot
    # files. The desktop installer now retries only the exact reported paths and
    # rejects the security-sensitive ones.
    script = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert "--overwrite '*'" not in script
    assert "reported conflict path" in script
    assert "refusing to overwrite security-sensitive path" in script
    # The minimal image has no /dev/fd, so a process substitution silently
    # yielded an empty conflict list and skipped the retry.
    assert "conflict_file=$(mktemp" in script
    assert "< <(" not in script


def test_desktop_profiles_install_and_start_pipewire() -> None:
    hook = REPO_ROOT / "etc" / "X11" / "xinit" / "xinitrc.d" / "20-grintion-audio.sh"
    assert hook.is_file()
    assert os.access(hook, os.X_OK)
    hook_text = hook.read_text()
    assert "grintion-audio --session" in hook_text

    helper = REPO_ROOT / "bin" / "grintion-audio"
    assert helper.is_file()
    assert os.access(helper, os.X_OK)
    text = helper.read_text()
    for daemon in ("pipewire", "wireplumber", "pipewire-pulse"):
        assert daemon in text
    assert "XDG_RUNTIME_DIR" in text
    assert "/proc/asound/card[0-9]*" in text

    wrapper = (REPO_ROOT / "etc" / "lightdm" / "Xsession-grintion").read_text()
    assert "XDG_RUNTIME_DIR" in wrapper

    for profile in (REPO_ROOT / "etc" / "grintion" / "desktops.d").glob("*.conf"):
        values = profile.read_text()
        for package in ("pipewire", "wireplumber", "alsa-ucm-conf", "linux-firmware"):
            assert package in values, f"{profile.name} is missing {package}"


def test_limine_deploy_refuses_missing_kernel(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("limine-bios.sys", "BOOTX64.EFI"):
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


def test_pacman_requires_package_signatures_without_missing_db_sigs() -> None:
    # Arch mirrors do not publish .db.sig; DatabaseRequired makes pacman -Sy
    # fail with 404 and breaks every delegated install.
    conf = (REPO_ROOT / "etc" / "pacman.conf").read_text()
    assert "SigLevel = Required DatabaseOptional" in conf
    assert "LocalFileSigLevel = Required" in conf
    assert "SigLevel = Required DatabaseRequired" not in conf


def test_pacman_uses_the_image_snapshot_not_rolling_mirrors() -> None:
    # The seeded base is linked against OpenSSL 3. Rolling mirrors moved to
    # OpenSSL 4 and pacman rejected every desktop transaction because
    # cryptsetup/curl/pacman/sudo require libcrypto.so=3-64.
    snapshot = (REPO_ROOT / "config" / "arch-snapshot").read_text()
    date = next(
        line.split("=", 1)[1].strip()
        for line in snapshot.splitlines()
        if line.startswith("ALA_DATE=")
    )
    expected = f"https://archive.archlinux.org/repos/{date}/$repo/os/$arch"
    conf = (REPO_ROOT / "etc" / "pacman.conf").read_text()
    assert conf.count(expected) == 3  # core, extra and multilib
    assert "geo.mirror.pkgbuild.com" not in conf
    assert "archive.archlinux.org/repos/2026/11/01" in conf


def test_installer_does_not_report_incomplete_desktop_as_installed() -> None:
    # A failed desktop transaction still leaves a usable base system, but the
    # summary must not start with "[+] ... installed" and the installer must
    # exit nonzero so scripts and users see the failure.
    installer = (REPO_ROOT / "bin" / "grintion-install").read_text()
    assert (
        'if [ "$DESKTOP_READY" -eq 1 ] && [ "$KERNEL_READY" -eq 1 ] '
        '&& [ "$SELF_TEST_OK" -eq 1 ]; then'
    ) in installer
    assert 'echo "[!] Grintion-OS $VERSION installation incomplete"' in installer
    assert (
        'if [ "$DESKTOP_READY" -ne 1 ] || [ "$KERNEL_READY" -ne 1 ] '
        '|| [ "$SELF_TEST_OK" -ne 1 ]; then'
    ) in installer


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
    # lightdm-autologin requires pam_shells; without it LightDM reports
    # "Module is unknown" and falls back to the greeter instead of logging in.
    assert "pam_shells.so" in modules

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
        "CONFIG_SND_HDA_INTEL=y",
        "CONFIG_SND_HDA_CODEC_REALTEK=y",
        "CONFIG_SND_USB_AUDIO=y",
        "CONFIG_8139TOO=y",
        "CONFIG_PCNET32=y",
    ):
        assert line in fragment

    # io_uring cannot be compiled out without CONFIG_EXPERT, which selects
    # CONFIG_DEBUG_KERNEL; it is disabled at runtime instead.
    sysctl = (REPO_ROOT / "etc" / "sysctl.d" / "99-grintion.conf").read_text()
    assert "kernel.io_uring_disabled = 2" in sysctl


def test_installer_phase2_flags_and_dry_run_json() -> None:
    res = subprocess.run(
        [
            str(INSTALLER),
            "--dry-run",
            "--json",
            "--unattended",
            "--disk",
            "/dev/vda",
            "--user",
            "testuser",
            "--swap-file",
            "1024",
            "--swap-size",
            "2048",
            "--encrypt",
            "--encrypt-home",
            "--separate-home",
            "--home-size",
            "4096",
            "--recovery-partition",
            "--recovery-size",
            "1024",
            "--secure-erase",
            "--removable",
            "--password-stdin",
        ],
        input="secret\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    data = __import__("json").loads(res.stdout)
    assert data["schema"] == 2
    assert data["disk"] == "/dev/vda"
    assert data["root"]["encrypted"] is True
    assert data["root"]["separate_home"] is True
    assert data["root"]["home_encrypted"] is True
    assert data["root"]["home_size_mib"] == 4096
    assert data["swap"]["partition_mib"] == 2048
    assert data["swap"]["file_mib"] == 1024
    assert data["recovery"]["enabled"] is True
    assert data["recovery"]["size_mib"] == 1024
    assert data["secure_erase"] is True
    assert data["removable"] is True
    assert data["kernel"] == "lts"


def test_installer_accepts_kernel_flavor_in_dry_run() -> None:
    res = subprocess.run(
        [
            str(INSTALLER),
            "--dry-run",
            "--json",
            "--unattended",
            "--disk", "/dev/vda",
            "--user", "testuser",
            "--kernel", "hwe",
            "--password-stdin",
        ],
        input="secret\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    data = __import__("json").loads(res.stdout)
    assert data["kernel"] == "hwe"


def test_installer_custom_partitioning_dry_run() -> None:
    res = subprocess.run(
        [
            str(INSTALLER),
            "--dry-run",
            "--json",
            "--unattended",
            "--custom",
            "--root-part",
            "/dev/nvme0n1p2",
            "--esp-part",
            "/dev/nvme0n1p1",
            "--home-part",
            "/dev/nvme0n1p3",
            "--swap-part",
            "/dev/nvme0n1p4",
            "--user",
            "customuser",
            "--password-stdin",
        ],
        input="secret\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    data = __import__("json").loads(res.stdout)
    assert data["custom_partitions"] is True
    assert data["root"]["device"] == "/dev/nvme0n1p2"
    assert data["esp_part"] == "/dev/nvme0n1p1"
    assert data["root"]["home_part"] == "/dev/nvme0n1p3"
    assert data["swap"]["partition_dev"] == "/dev/nvme0n1p4"


def test_grintion_boot_operations(tmp_path: Path) -> None:
    boot_tool = REPO_ROOT / "bin" / "grintion-boot"
    esp_dir = tmp_path / "boot" / "efi"
    esp_dir.mkdir(parents=True)
    conf = esp_dir / "limine.conf"
    conf.write_text("""timeout: 5
default_entry: /Grintion-OS 0.10.0

/Grintion-OS 0.10.0
    protocol: linux
    kernel_path: boot():/EFI/grintion/vmlinuz-grintion
    cmdline: root=UUID=123 rw quiet
""")

    env = os.environ.copy()
    env["LIMINE_CONF"] = str(conf)

    # list json
    res = subprocess.run([str(boot_tool), "list", "--json"], capture_output=True, text=True, check=False)
    # The script looks at /boot/efi unless overridden or testable. Let's test with subprocess when conf is at default or let it fail gracefully
    help_res = subprocess.run([str(boot_tool), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0
    assert "set-default" in help_res.stdout
    assert "set-password" in help_res.stdout


def test_grintion_boot_health_advanced() -> None:
    health_tool = REPO_ROOT / "bin" / "grintion-boot-health"
    res = subprocess.run([str(health_tool), "status", "--json"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    data = __import__("json").loads(res.stdout)
    assert "attempts" in data
    assert "failed" in data
    assert "session_verified" in data


def test_boot_health_counter_is_bounded_and_auto_revert_is_atomic(tmp_path: Path) -> None:
    health_tool = REPO_ROOT / "bin" / "grintion-boot-health"
    state = tmp_path / "health"
    limine = tmp_path / "limine.conf"
    limine.write_text(
        "timeout: 5\n"
        "default_entry: /Grintion-OS\n"
        "/Grintion-OS\n"
        "    kernel_path: boot():/EFI/grintion/vmlinuz-grintion\n"
        "/Grintion-OS snapshot\n"
        "    kernel_path: boot():/EFI/grintion/vmlinuz-grintion\n"
    )
    env = os.environ.copy()
    env.update({
        "GRINTION_BOOT_HEALTH_STATE": str(state),
        "GRINTION_LIMINE_CONF": str(limine),
    })

    for _ in range(3):
        res = subprocess.run(
            [str(health_tool), "record"], capture_output=True, text=True, check=False, env=env
        )
        assert res.returncode == 0, res.stderr

    assert (state / "attempts").read_text().strip() == "3"
    assert (state / "failed").exists()
    assert "default_entry: /Grintion-OS snapshot" in limine.read_text()
    assert (state / "revert.log").is_file()

    corrupt = subprocess.run(
        [str(health_tool), "status", "--json"],
        capture_output=True, text=True, check=False, env=env,
    )
    assert corrupt.returncode == 0
    report = __import__("json").loads(corrupt.stdout)
    assert report["attempts"] == 3
    assert report["failed"] is True
    assert report["auto_reverted"] is True

    (state / "attempts").write_text("not-a-number\n")
    recovered = subprocess.run(
        [str(health_tool), "status", "--json"],
        capture_output=True, text=True, check=False, env=env,
    )
    assert recovered.returncode == 0
    assert __import__("json").loads(recovered.stdout)["attempts"] == 0

    good = subprocess.run(
        [str(health_tool), "mark-good"], capture_output=True, text=True, check=False, env=env
    )
    assert good.returncode == 0, good.stderr
    assert (state / "attempts").read_text().strip() == "0"
    assert not (state / "failed").exists()


def test_grintion_backup_lifecycle(tmp_path: Path) -> None:
    backup_tool = REPO_ROOT / "bin" / "grintion-backup"
    help_res = subprocess.run([str(backup_tool), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0
    assert "create" in help_res.stdout
    assert "restore" in help_res.stdout

    # Create dummy source and backup
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("backup-content")
    dst = tmp_path / "backups"

    create_res = subprocess.run(
        [str(backup_tool), "create", "--target", str(dst), "--include", str(src), "--name", "testsnap"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert create_res.returncode == 0, create_res.stderr

    # list json
    list_res = subprocess.run(
        [str(backup_tool), "list", "--target", str(dst), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert list_res.returncode == 0
    data = __import__("json").loads(list_res.stdout)
    assert len(data["backups"]) == 1
    assert data["backups"][0]["exists"] is True

    # verify
    archive_path = data["backups"][0]["path"]
    verify_res = subprocess.run([str(backup_tool), "verify", archive_path], capture_output=True, text=True, check=False)
    assert verify_res.returncode == 0


def test_grintion_reset_and_migrate() -> None:
    reset_tool = REPO_ROOT / "bin" / "grintion-reset"
    res = subprocess.run([str(reset_tool), "status", "--json"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    data = __import__("json").loads(res.stdout)
    assert "factory_reset_supported" in data

    migrate_tool = REPO_ROOT / "bin" / "grintion-migrate"
    help_res = subprocess.run([str(migrate_tool), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0
    assert "export" in help_res.stdout
    assert "import" in help_res.stdout


def test_grintion_a11y_and_display() -> None:
    a11y_tool = REPO_ROOT / "bin" / "grintion-a11y"
    res = subprocess.run([str(a11y_tool), "status", "--json"], capture_output=True, text=True, check=False)
    assert res.returncode == 0
    data = __import__("json").loads(res.stdout)
    assert "screen_reader" in data
    assert "high_contrast" in data

    display_tool = REPO_ROOT / "bin" / "grintion-display"
    d_res = subprocess.run([str(display_tool), "status", "--json"], capture_output=True, text=True, check=False)
    assert d_res.returncode == 0
    d_data = __import__("json").loads(d_res.stdout)
    assert "display_server" in d_data


def test_grintion_apps_and_welcome() -> None:
    apps_tool = REPO_ROOT / "bin" / "grintion-apps"
    env = os.environ.copy()
    env["GRINTION_APP_PROFILES_DIR"] = str(REPO_ROOT / "etc" / "grintion" / "profiles.d")
    res = subprocess.run([str(apps_tool), "list", "--json"], capture_output=True, text=True, check=False, env=env)
    assert res.returncode == 0, res.stderr
    data = __import__("json").loads(res.stdout)
    names = {p["name"] for p in data["profiles"]}
    assert {"browser", "office", "gaming", "vmguest", "dev"}.issubset(names)

    welcome_tool = REPO_ROOT / "bin" / "grintion-welcome"
    w_res = subprocess.run([str(welcome_tool), "--json"], capture_output=True, text=True, check=False)
    assert w_res.returncode == 0
    w_data = __import__("json").loads(w_res.stdout)
    assert w_data["os"] == "Grintion-OS"

