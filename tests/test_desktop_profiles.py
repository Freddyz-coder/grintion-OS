from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DESKTOP = REPO_ROOT / "bin" / "grintion-desktop"
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
            assert values["DM_BIN"] == "", path
            assert values["XINITRC"] == "", path


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
