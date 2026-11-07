from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP = REPO_ROOT / "bin" / "grintion-desktop"
SESSION = REPO_ROOT / "bin" / "grintion-session"
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
    groups = (REPO_ROOT / "etc" / "group").read_text()
    assert "seat:x:" in groups
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
