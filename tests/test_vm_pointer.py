from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_bin(name: str) -> Path:
    p = REPO_ROOT / "bin" / name
    if p.exists():
        return p
    clean = name.removeprefix("grintion-")
    p_clean = REPO_ROOT / "bin" / clean
    if p_clean.exists():
        return p_clean
    p_pref = REPO_ROOT / "bin" / f"grintion-{clean}"
    if p_pref.exists():
        return p_pref
    return p


POINTER = get_bin("pointer-sync")
XORG_INPUT = get_bin("xorg-input")
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


DEVICES_MULTIWORD_ZERO_ABS = """\
I: Bus=0003 Vendor=1234 Product=0001 Version=0001
N: Name="Some HID Device"
H: Handlers=mouse0 event3
B: ABS=0 0 0
B: REL=0

I: Bus=0011 Vendor=0002 Product=0001 Version=0001
N: Name="QEMU PS/2 Mouse"
H: Handlers=mouse1 event4
B: REL=103
B: KEY=70000 0 0 0 0
"""

DEVICES_TOUCHPAD = """\
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
N: Name="SynPS/2 Synaptics TouchPad"
H: Handlers=mouse2 event3
B: ABS=100013fffff
B: KEY=e520 10000 0 0 0 0

I: Bus=0011 Vendor=0002 Product=0001 Version=0001
N: Name="QEMU PS/2 Mouse"
H: Handlers=mouse1 event2
B: REL=103
B: KEY=70000 0 0 0 0
"""

GREETD_SERVICE = REPO_ROOT / "etc" / "sv" / "greetd" / "run"


def test_duplicate_relative_mouse_is_ignored_when_tablet_exists(tmp_path: Path) -> None:
    result = run_pointer(tmp_path, DEVICES, "--no-reload")
    assert result.returncode == 0, result.stderr
    rule = (tmp_path / "rules" / "99-grintion-pointer-sync.rules").read_text()
    assert 'ATTRS{name}=="QEMU PS/2 Mouse"' in rule
    assert 'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in rule
    assert "QEMU USB Tablet" not in rule
    assert (tmp_path / "marker").is_file()


def test_multiword_zero_abs_line_is_not_treated_as_absolute_pointer(tmp_path: Path) -> None:
    """Regression: 'B: ABS=0 0 0' (all words zero) must not trigger the tablet path.

    The old ``re.search`` negative look-ahead only anchored to the end of the
    full line, so ``B: ABS=0 0 0`` was incorrectly matched by the leading ``=0``
    before the spaces, causing pointer-sync to believe an absolute tablet was
    present and suppressing the real relative mouse.
    """
    result = run_pointer(tmp_path, DEVICES_MULTIWORD_ZERO_ABS, "--no-reload")
    assert result.returncode == 0, result.stderr
    # No absolute tablet → rule file must NOT be written.
    rules = tmp_path / "rules" / "99-grintion-pointer-sync.rules"
    assert not rules.exists(), (
        "pointer-sync wrote a rule even though B: ABS=0 0 0 (all zero) is not a tablet"
    )
    assert "keeping relative pointer" in result.stdout


def test_touchpad_abs_axes_do_not_suppress_relative_mouse(tmp_path: Path) -> None:
    """A touchpad (ABS with MT bits) must not be classified as the VM tablet.

    When a system has both a QEMU USB Tablet and a Synaptics TouchPad the
    tablet is recognised as the absolute pointer and the duplicate PS/2 mouse
    is suppressed.  The touchpad itself must not appear in the ignore rule
    (it is already the preferred input device via its own libinput profile).
    """
    result = run_pointer(tmp_path, DEVICES_TOUCHPAD, "--no-reload")
    assert result.returncode == 0, result.stderr
    rule = (tmp_path / "rules" / "99-grintion-pointer-sync.rules").read_text()
    assert 'ATTRS{name}=="QEMU PS/2 Mouse"' in rule
    assert 'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in rule
    # The touchpad must not be ignored — it has MT axes so it is not the tablet.
    assert "SynPS/2 Synaptics TouchPad" not in rule


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


def test_greetd_service_runs_pointer_sync_before_compositor() -> None:
    """greetd (used by Sway/KDE Wayland) must also run pointer-sync first.

    Without this, Wayland compositors receive both pointer streams and
    exhibit the same mouse desynchronisation as Xorg sessions did before
    the display-manager service was fixed.
    """
    service = GREETD_SERVICE.read_text()
    assert "grintion-pointer-sync" in service, (
        "greetd service does not call grintion-pointer-sync; "
        "Wayland sessions (Sway, KDE) will have mouse desynchronisation"
    )
    # pointer-sync must precede the exec greetd line
    assert service.index("grintion-pointer-sync") < service.index("exec /usr/bin/greetd")
