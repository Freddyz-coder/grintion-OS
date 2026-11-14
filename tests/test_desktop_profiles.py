from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP = REPO_ROOT / "bin" / "grintion-desktop"
SESSION = REPO_ROOT / "bin" / "grintion-session"
INSTALL = REPO_ROOT / "bin" / "grintion-install"
AUDIO = REPO_ROOT / "bin" / "grintion-audio"
PROFILES = REPO_ROOT / "etc" / "grintion" / "desktops.d"


def read_profile(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def test_every_profile_has_required_fields() -> None:
    profiles = sorted(PROFILES.glob("*.conf"))
    assert {path.stem for path in profiles} == {"xfce", "gnome", "kde", "lxqt", "sway", "i3"}
    for path in profiles:
        values = read_profile(path)
        assert values["NAME"] == path.stem
        assert values["PACKAGES"], path
        assert values["DISPLAY_SERVER"] in {"x11", "wayland", "wayland/x11"}, path
        if values["DISPLAY_SERVER"] == "wayland":
            # KDE keeps SDDM but has no X11 session to start; Sway has no DM.
            assert values["XINITRC"] == "", path
        if values["NAME"] == "sway":
            assert values["DM_BIN"] == "", path
        if values["NAME"] == "kde":
            assert "startplasma-x11" not in values["XINITRC"]


def test_graphical_profiles_install_and_enable_networkmanager() -> None:
    # KDE's plasma-meta pulls in networkmanager, but the base image's service is
    # dhcpcd and has no D-Bus API. The applet then reports "NetworkManager
    # service not running" even though the package is installed. Every profile
    # must install the backend explicitly, and the GTK applets need nm-applet.
    for path in sorted(PROFILES.glob("*.conf")):
        values = read_profile(path)
        packages = values["PACKAGES"].split()
        assert "networkmanager" in packages, path
        if values["NAME"] == "kde":
            assert "plasma-nm" in packages, path
        elif values["NAME"] != "gnome":
            assert "network-manager-applet" in packages, path


def test_networkmanager_service_is_tracked_and_wired() -> None:
    service = (REPO_ROOT / "etc" / "sv" / "NetworkManager" / "run").read_text()
    assert os.access(REPO_ROOT / "etc" / "sv" / "NetworkManager" / "run", os.X_OK)
    assert "exec /usr/bin/NetworkManager --no-daemon" in service
    assert "systemctl" not in service
    assert "/run/dbus/system_bus_socket" in service
    assert "/var/log/NetworkManager.log" in service

    config = (REPO_ROOT / "etc" / "NetworkManager" / "conf.d" / "10-grintion.conf").read_text()
    assert "dhcp=internal" in config
    assert "rc-manager=file" in config

    desktop = DESKTOP.read_text()
    assert "enable_network_manager" in desktop
    assert 'ln -sfn "/etc/sv/NetworkManager"' in desktop
    assert "var/service/network" in desktop
    assert "for _ in $(seq 1 40)" in desktop
    assert 'list|drivers|status|network)' in desktop
    assert "network) cmd_network" in desktop


def test_list_json_reports_profiles() -> None:
    env = os.environ.copy()
    env["GRINTION_DESKTOP_PROFILE_DIR"] = str(PROFILES)
    result = subprocess.run(
        [str(DESKTOP), "list", "--json"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    by_name = {entry["name"]: entry for entry in data}
    assert set(by_name) == {"xfce", "gnome", "kde", "lxqt", "sway", "i3"}
    assert "xfce4" in by_name["xfce"]["packages"]
    assert by_name["xfce"]["xinitrc"] == "exec startxfce4"
    assert by_name["xfce"]["display_manager"] == "lightdm lightdm-gtk-greeter"
    assert by_name["sway"]["display_server"] == "wayland"
    assert by_name["sway"]["xinitrc"] == ""
    assert by_name["kde"]["display_server"] == "wayland"
    assert by_name["kde"]["xinitrc"] == ""


def test_wayland_profiles_install_portals_and_seat_stack() -> None:
    desktop = DESKTOP.read_text()
    assert "enable_wayland_seat" in desktop
    assert 'ln -sfn "/etc/sv/seatd"' in desktop
    assert '[[ "${DISPLAY_SERVER:-}" == *wayland* ]]' in desktop
    for name, portal in {
        "xfce": "xdg-desktop-portal-gtk",
        "gnome": "xdg-desktop-portal-gtk",
        "kde": "xdg-desktop-portal-kde",
        "lxqt": "xdg-desktop-portal-gtk",
        "sway": "xdg-desktop-portal-wlr",
        "i3": "xdg-desktop-portal-gtk",
    }.items():
        profile = (PROFILES / f"{name}.conf").read_text()
        assert "xdg-desktop-portal" in profile, name
        assert portal in profile, name


def test_session_wrapper_exports_wayland_environment(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = str(tmp_path / "runtime")
    result = subprocess.run(
        [str(SESSION), "--type", "wayland", "--desktop", "sway", "--", "env"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "XDG_SESSION_TYPE=wayland" in result.stdout
    assert "XDG_CURRENT_DESKTOP=sway" in result.stdout
    assert "SEATD_SOCK=/run/seatd.sock" in result.stdout
    assert f"XDG_RUNTIME_DIR={tmp_path / 'runtime'}" in result.stdout


def test_rootfs_ships_the_dbus_session_configuration() -> None:
    # dbus-run-session fails immediately if session.conf is not in the image.
    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert "/usr/share/dbus-1" in rootfs
    assert "cp -a /usr/share/dbus-1/." in rootfs


def test_seatd_service_and_group_are_tracked() -> None:
    service = (REPO_ROOT / "etc" / "sv" / "seatd" / "run").read_text()
    assert "seatd -g seat" in service
    assert "/run/seatd.sock" in service
    import tomllib

    manifest = tomllib.loads((REPO_ROOT / "config" / "accounts.toml").read_text())
    groups = {group["name"] for group in manifest["group"]}
    assert "seat" in groups
    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert "seatd" in rootfs
    assert "seatd" in (REPO_ROOT / "config" / "rootfs.required-binaries").read_text()


def test_udev_service_is_the_standalone_device_manager() -> None:
    service = (REPO_ROOT / "etc" / "sv" / "udev" / "run").read_text()
    assert "/usr/lib/systemd/systemd-udevd &" in service
    assert "udevadm trigger" in service
    assert "systemd --" not in service
    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert "systemd-udevd" in rootfs
    assert "udevadm" in (REPO_ROOT / "config" / "rootfs.required-binaries").read_text()
    session = (REPO_ROOT / "bin" / "grintion-session").read_text()
    assert "/run/udev/control" in session
    # systemd-udevd's interface-name and rule diagnostics must not interleave
    # with the login prompt.
    assert "exec >>/var/log/udev.log 2>&1" in service
    assert "GROUP=" in rootfs and "udev group" in rootfs


def test_sddm_wayland_session_gets_a_runtime_directory() -> None:
    # Without logind/pam_systemd SDDM's Wayland session had no writable
    # XDG_RUNTIME_DIR and KWin exited with "Could not create wayland socket".
    wrapper = REPO_ROOT / "etc" / "sddm" / "wayland-session-grintion"
    assert wrapper.is_file()
    assert os.access(wrapper, os.X_OK)
    text = wrapper.read_text()
    assert "XDG_RUNTIME_DIR" in text
    assert "stat -c %u" in text
    assert 'exec /usr/share/sddm/scripts/wayland-session "$@"' in text

    desktop = DESKTOP.read_text()
    assert "configure_sddm_wayland" in desktop
    assert "SessionCommand=/etc/sddm/wayland-session-grintion" in desktop


def test_human_accounts_get_graphics_sound_and_input_groups() -> None:
    # Nothing applies udev/pam ACLs without logind: /dev/dri/card0 is
    # root:video, /dev/snd/* root:audio and /dev/input/* root:input, so a
    # session owned only by wheel cannot start a Wayland compositor.
    text = DESKTOP.read_text()
    assert "grant_session_groups" in text
    assert 'wanted = ["video", "audio", "input", "render"]' in text
    assert 'wanted.append("seat")' in text
    # Duplicate group lines made usermod refuse with "Multiple entries named
    # 'render'"; the function collapses them before adding members.
    assert "if not line.strip() or name in seen" in text


def test_wayland_profiles_complete_the_seat_library() -> None:
    # Arch's seatd package replaces libseat and ships libseat.so.1. The base
    # image carries the seeded seatd binary, so pacman can report the package
    # as installed while the library is absent; listing seatd in the profile
    # forces the full reinstall and the installer verifies the result.
    for name in ("sway", "kde"):
        packages = read_profile(PROFILES / f"{name}.conf")["PACKAGES"].split()
        assert "seatd" in packages, name
    desktop = DESKTOP.read_text()
    assert 'compgen -G "$TARGET_ROOT/usr/lib/libseat.so*"' in desktop
    assert "libseat.so is missing" in desktop


def test_lxqt_ships_a_greeter_session_entry() -> None:
    entry = (REPO_ROOT / "etc" / "grintion" / "sessions" / "lxqt.desktop").read_text()
    assert "Exec=startlxqt" in entry
    assert "TryExec=startlxqt" in entry
    assert "DesktopNames=LXQt" in entry
    assert "install_session_desktop" in DESKTOP.read_text()


def test_console_login_provides_a_runtime_directory() -> None:
    # sway and PipeWire refuse to start without XDG_RUNTIME_DIR, and a plain
    # getty login has no logind to create one.
    text = (REPO_ROOT / "etc" / "profile.d" / "00-grintion-runtime.sh").read_text()
    assert "XDG_RUNTIME_DIR" in text
    assert "/tmp/grintion-runtime-" in text
    assert "SEATD_SOCK" in text


def test_sway_installs_a_user_config_and_audio_hook() -> None:
    desktop = DESKTOP.read_text()
    assert "configure_sway_config" in desktop
    assert "include /etc/sway/config.d/*" in desktop
    snippet = (REPO_ROOT / "etc" / "sway" / "config.d" / "50-grintion-session.conf").read_text()
    assert "exec grintion-audio --session" in snippet
    entry = (REPO_ROOT / "etc" / "grintion" / "sessions" / "sway.desktop").read_text()
    assert "Exec=sway" in entry


def test_gnome_installation_is_refused_without_systemd() -> None:
    # gnome-session 51 starts org.gnome.Shell through org.freedesktop.systemd1
    # and aborts with "Failed to start unit" when it is missing. Verify the
    # profile does not pretend to install a working desktop.
    values = read_profile(PROFILES / "gnome.conf")
    assert values.get("REQUIRES_SYSTEMD") == "1"
    desktop = DESKTOP.read_text()
    assert "requires the systemd user session manager" in desktop
    assert "[2] GNOME" not in desktop
    assert "xfce/gnome" not in desktop
    assert "[5] i3" in desktop


def test_lxqt_uses_the_verified_lightdm_x11_path() -> None:
    # SDDM was never rendered in this runit image. LightDM/Xorg is the path
    # that is verified for XFCE and i3, and LXQt is an X11 session.
    values = read_profile(PROFILES / "lxqt.conf")
    assert values["DISPLAY_SERVER"] == "x11"
    assert values["DM"] == "lightdm lightdm-gtk-greeter"
    assert values["DM_BIN"] == "/usr/bin/lightdm"
    assert values["XINITRC"] == "exec startlxqt"


def test_audio_startup_is_shared_by_x11_and_wayland() -> None:
    helper = AUDIO
    assert helper.is_file()
    assert os.access(helper, os.X_OK)
    text = helper.read_text()
    assert "for card in /proc/asound/card[0-9]*" in text
    assert 'amixer -c "$index"' in text
    assert not (REPO_ROOT / "etc" / "pipewire" / "pipewire.conf.d" / "50-grintion-alsa.conf").exists()

    hook = (
        REPO_ROOT / "etc" / "X11" / "xinit" / "xinitrc.d" / "20-grintion-audio.sh"
    ).read_text()
    assert "grintion-audio --session" in hook

    autostart = (
        REPO_ROOT / "etc" / "xdg" / "autostart" / "grintion-audio.desktop"
    ).read_text()
    assert "Exec=/usr/bin/grintion-audio --session" in autostart

    session = SESSION.read_text()
    assert "exec dbus-run-session --" in session
    assert session.count("/etc/X11/xinit/xinitrc.d/20-grintion-audio.sh") >= 2


def test_profiles_include_firmware_and_wireless_regulatory_data() -> None:
    # A desktop profile without firmware cannot drive Intel/AMD/Realtek Wi-Fi
    # or GPU blocks even when the kernel module is present.
    for path in PROFILES.glob("*.conf"):
        values = read_profile(path)
        assert "linux-firmware" in values["PACKAGES"].split(), path
        assert "wireless-regdb" in values["PACKAGES"].split(), path


def test_kernel_has_common_wireless_drivers() -> None:
    config = (REPO_ROOT / "config" / "kernel-hardened.config").read_text()
    for symbol in (
        "CONFIG_CFG80211=m",
        "CONFIG_MAC80211=m",
        "CONFIG_IWLWIFI=m",
        "CONFIG_IWLMVM=m",
        "CONFIG_RTW88=m",
        "CONFIG_RTW89=m",
        "CONFIG_MT7921E=m",
        "CONFIG_ATH10K=m",
        "CONFIG_ATH11K=m",
        "CONFIG_BRCMFMAC=m",
        "CONFIG_RTL8XXXU=m",
    ):
        assert symbol in config, symbol


def test_build_installs_tools_only_in_usr_bin() -> None:
    # Root's PATH searches /usr/sbin before /usr/bin. Installing every tool
    # into both places meant an updated /usr/bin/grintion-desktop was shadowed
    # by the stale /usr/sbin copy, so installer fixes never took effect.
    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert 'install -D -m 0755 "$tool_path" "$ROOTFS/usr/bin/$tool"' in rootfs
    assert '"$tool_path" "$ROOTFS/usr/sbin/$tool"' not in rootfs


def test_installer_validates_desktop_before_disk_operations() -> None:
    text = INSTALL.read_text()
    validation = text.index('desktop_profile="$DESKTOP"')
    first_partition = text.index('parted -s "$DISK" mklabel')
    assert validation < first_partition
    assert "unknown desktop environment" in text
