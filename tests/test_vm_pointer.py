from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POINTER = REPO_ROOT / "bin" / "grintion-pointer-sync"
XORG_INPUT = REPO_ROOT / "bin" / "grintion-xorg-input"
DESKTOP_SERVICE = REPO_ROOT / "etc" / "sv" / "display-manager" / "run"
PROFILES = REPO_ROOT / "etc" / "grintion" / "desktops.d"

DEVICES = """\
I: Bus=0011 Vendor=0001 Product=0001 Version=0001
N: Name="AT Translated Set 2 keyboard"
H: Handlers=sysrq kbd event0
B: KEY=402000000 3803078f800d001 feffffdfffefffff fffffffffffffffe

I: Bus=0003 Vendor=0627 Product=0001 Version=0001
N: Name="QEMU USB Tablet"
H: Handlers=mouse0 event1
B: REL=0
B: ABS=3
B: KEY=70000 0 0 0 0

I: Bus=0011 Vendor=0002 Product=0001 Version=0001
N: Name="QEMU PS/2 Mouse"
H: Handlers=mouse1 event2
B: REL=103
B: KEY=70000 0 0 0 0
"""


def run_pointer(tmp_path: Path, devices: str = DEVICES, *args: str) -> subprocess.CompletedProcess:
    source = tmp_path / "devices"
    source.write_text(devices)
    env = os.environ.copy()
    env["GRINTION_INPUT_DEVICES"] = str(source)
    env["GRINTION_UDEV_RULES_DIR"] = str(tmp_path / "rules")
    env["GRINTION_POINTER_MARKER"] = str(tmp_path / "marker")
    return subprocess.run(
        [str(POINTER), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_duplicate_relative_mouse_is_ignored_when_tablet_exists(tmp_path: Path) -> None:
    result = run_pointer(tmp_path, DEVICES, "--no-reload")
    assert result.returncode == 0, result.stderr
    rule = (tmp_path / "rules" / "99-grintion-pointer-sync.rules").read_text()
    assert 'ATTRS{name}=="QEMU PS/2 Mouse"' in rule
    assert 'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in rule
    assert "QEMU USB Tablet" not in rule
    assert (tmp_path / "marker").is_file()


def test_relative_mouse_is_kept_without_an_absolute_pointer(tmp_path: Path) -> None:
    relative_only = (
        DEVICES.replace('N: Name="QEMU USB Tablet"', 'N: Name="QEMU Virtual Mouse"')
        .replace("B: ABS=3", "B: ABS=0")
    )
    result = run_pointer(tmp_path, relative_only, "--no-reload")
    assert result.returncode == 0, result.stderr
    assert "keeping relative pointer" in result.stdout
    rules = tmp_path / "rules" / "99-grintion-pointer-sync.rules"
    assert not rules.exists()


def test_xorg_prefers_libinput_and_display_manager_runs_pointer_sync() -> None:
    # Explicit evdev sections and libinput hotplug both owning the same event
    # node gave Xorg two pointers. The fallback is now only used when udev or
    # the libinput driver is unavailable.
    text = XORG_INPUT.read_text()
    assert "/run/udev/control" in text
    assert "libinput_drv.so" in text
    assert "rm -f" in text
    service = DESKTOP_SERVICE.read_text()
    assert "grintion-pointer-sync" in service
    assert service.index("grintion-pointer-sync") < service.index("grintion-xorg-input")
    for name in ("xfce", "kde", "lxqt", "i3"):
        profile = (PROFILES / f"{name}.conf").read_text()
        assert "xf86-input-libinput" in profile, name
