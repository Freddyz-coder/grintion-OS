from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"
LAPTOP_DB = REPO_ROOT / "etc" / "grintion" / "laptop-support.json"
HCL_DB = REPO_ROOT / "etc" / "grintion" / "hcl.json"

VENDOR_CASES = [
    ("lenovo", "LENOVO", "ThinkPad T14 Gen 5", "thinkpad_acpi", "ThinkPad"),
    ("hp", "HP", "EliteBook 840 G10", "hp_wmi", "EliteBook"),
    ("dell", "Dell Inc.", "Latitude 5440", "dell_laptop", "Latitude"),
    ("acer", "Acer", "Aspire 5 A515", "acer_wmi", "Aspire"),
    ("asus", "ASUSTeK COMPUTER INC.", "ZenBook 14 UX3405", "asus_wmi", "ZenBook"),
    ("msi", "Micro-Star International Co., Ltd.", "Katana 15 B13V", "msi_ec", "Katana"),
    ("samsung", "SAMSUNG ELECTRONICS CO., LTD.", "Galaxy Book4 Pro", "samsung_laptop", "Galaxy Book"),
]


def get_bin(name: str) -> Path:
    for candidate in (
        name,
        name.removeprefix("grintion-"),
        f"grintion-{name.removeprefix('grintion-')}",
    ):
        path = BIN_DIR / candidate
        if path.exists():
            return path
    raise AssertionError(f"missing test binary: {name}")


def run_bin(name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        [str(get_bin(name)), *args],
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_driver_select():
    loader = SourceFileLoader(
        "grintion_driver_select", str(BIN_DIR / "driver-select")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def make_fake_machine(
    tmp_path: Path,
    vendor: str,
    product: str,
    chassis: str = "10",
    audio: bool = True,
) -> dict[str, str]:
    sysfs = tmp_path / "sys"
    dmi = sysfs / "class" / "dmi" / "id"
    write(dmi / "sys_vendor", vendor + "\n")
    write(dmi / "product_name", product + "\n")
    write(dmi / "chassis_type", chassis + "\n")
    write(dmi / "board_name", "Grintion Test Board\n")
    write(dmi / "bios_version", "1.0.0\n")

    pci = sysfs / "bus" / "pci" / "devices"
    wifi = pci / "0000:03:00.0"
    write(wifi / "class", "0x028000\n")
    write(wifi / "vendor", "0x8086\n")
    write(wifi / "device", "0xa0f0\n")
    write(
        wifi / "modalias",
        "pci:v00008086d0000A0F0sv00008086sd00000001bc02sc80i00\n",
    )

    usb = pci / "0000:00:14.0"
    write(usb / "class", "0x0c0330\n")
    write(usb / "vendor", "0x8086\n")
    write(usb / "device", "0xa0ed\n")
    write(
        usb / "modalias",
        "pci:v00008086d0000A0EDsv00008086sd00000001bc0csc03i30\n",
    )

    alias_lines = [
        "alias pci:v00008086d0000A0F0sv*sd*bc*sc*i* iwlwifi\n",
    ]
    if audio:
        sound = pci / "0000:00:1f.3"
        write(sound / "class", "0x040300\n")
        write(sound / "vendor", "0x8086\n")
        write(sound / "device", "0xa0c8\n")
        write(
            sound / "modalias",
            "pci:v00008086d0000A0C8sv00008086sd00000001bc04sc03i00\n",
        )
        alias_lines.append(
            "alias pci:v00008086d0000A0C8sv*sd*bc*sc*i* snd_sof_pci_intel_tgl\n"
        )

    modules = tmp_path / "modules"
    write(modules / "modules.alias", "".join(alias_lines))
    write(modules / "modules.builtin", "")

    modinfo = tmp_path / "modinfo"
    write(
        modinfo,
        "#!/bin/sh\n"
        'if [ "$1" = "-F" ] && [ "$2" = "firmware" ]; then\n'
        '    case "$3" in\n'
        "        iwlwifi) printf '%s\\n' iwlwifi-cc-a0-77.ucode ;;\n"
        "        snd_sof*) printf '%s\\n' intel/sof/sof-tgl.ri ;;\n"
        "    esac\n"
        "    exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    modinfo.chmod(0o755)

    firmware = tmp_path / "firmware"
    firmware.mkdir()
    (sysfs / "class" / "net").mkdir(parents=True)
    (sysfs / "class" / "tpm").mkdir(parents=True)

    return {
        "GRINTION_SYSFS": str(sysfs),
        "GRINTION_MODULES_DIR": str(modules),
        "GRINTION_MODINFO": str(modinfo),
        "GRINTION_FIRMWARE_DIRS": str(firmware),
        "GRINTION_LAPTOP_DB": str(LAPTOP_DB),
        "GRINTION_SYSFS_DMI": str(dmi),
        "GRINTION_SYSFS_PCI": str(pci),
        "GRINTION_SYSFS_NET": str(sysfs / "class" / "net"),
        "GRINTION_SYSFS_TPM": str(sysfs / "class" / "tpm"),
    }


def test_laptop_matrix_covers_every_requested_vendor() -> None:
    data = json.loads(LAPTOP_DB.read_text(encoding="utf-8"))
    assert data["schema"] >= 1
    profiles = {profile["id"]: profile for profile in data["vendors"]}
    for vendor_id, _vendor, _product, _module, family in VENDOR_CASES:
        profile = profiles[vendor_id]
        assert profile["aliases"], vendor_id
        assert profile["families"], vendor_id
        assert family in {entry["name"] for entry in profile["families"]}
        assert profile["platform_modules"], vendor_id
        assert "alsa-ucm-conf" in profile["packages"]
        for feature in ("wifi", "storage", "firmware", "audio", "ports"):
            assert profile["features"][feature], (vendor_id, feature)
    assert {"default_packages", "chassis_types"} <= set(data)


def test_driver_select_matches_each_vendor_and_installs_laptop_support(tmp_path: Path) -> None:
    for offset, (vendor_id, vendor, product, module, family) in enumerate(VENDOR_CASES):
        machine = tmp_path / f"machine-{offset}"
        machine.mkdir()
        env = make_fake_machine(machine, vendor, product)
        result = run_bin("grintion-driver-select", "--json", "--root", str(machine), env=env)
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        platform = data["platform"]
        assert platform["detected"] is True, vendor_id
        assert platform["laptop"] is True, vendor_id
        assert platform["profile"] == vendor_id, vendor_id
        assert platform["family"] == family, vendor_id
        assert module in platform["modules"], vendor_id
        assert "alsa-ucm-conf" in platform["packages"], vendor_id
        assert "sof-firmware" in platform["packages"], vendor_id
        assert "linux-firmware-intel" in data["packages"], vendor_id
        assert "iwlwifi" in data["modules"], vendor_id
        assert module not in data["initramfs_modules"], vendor_id
        assert (machine / "etc/grintion/hardware-profile.json").is_file()
        modules_conf = (machine / "etc/modules-load.d/grintion-hardware.conf").read_text()
        assert module in modules_conf
        initramfs = run_bin(
            "grintion-driver-select", "--initramfs-modules", "--root", str(machine), env=env
        )
        assert initramfs.returncode == 0, initramfs.stderr
        assert "iwlwifi" in initramfs.stdout
        assert module not in initramfs.stdout


def test_driver_select_retries_packages_individually_after_a_combined_failure(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "root"
    pacman = root / "usr/bin/pacman"
    log = tmp_path / "pacman.log"
    write(
        pacman,
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> "$FAKE_PACMAN_LOG"\n'
        'if [ "$#" -gt 4 ]; then exit 1; fi\n'
        "exit 0\n",
    )
    pacman.chmod(0o755)

    fakebin = tmp_path / "bin"
    chroot = fakebin / "chroot"
    write(
        chroot,
        "#!/bin/sh\n"
        "root=$1; shift\n"
        "cmd=$1; shift\n"
        'case "$cmd" in /usr/bin/*) cmd="$root$cmd" ;; esac\n'
        'exec "$cmd" "$@"\n',
    )
    chroot.chmod(0o755)
    monkeypatch.setenv("PATH", str(fakebin) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("FAKE_PACMAN_LOG", str(log))

    module = load_driver_select()
    ok, message = module.install_packages(["linux-firmware-intel", "sof-firmware"], root)
    assert ok is True
    assert "individually" in message
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert "linux-firmware-intel sof-firmware" in lines[0]
    assert lines[1].endswith("linux-firmware-intel")
    assert lines[2].endswith("sof-firmware")


def test_driver_select_does_not_apply_laptop_profile_to_a_desktop(tmp_path: Path) -> None:
    env = make_fake_machine(tmp_path, "LENOVO", "ThinkCentre M90q", chassis="3", audio=False)
    result = run_bin("grintion-driver-select", "--json", "--root", str(tmp_path), env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    platform = data["platform"]
    assert platform["laptop"] is False
    assert platform["detected"] is False
    assert platform["profile"] == ""
    assert platform["packages"] == []
    assert platform["modules"] == []
    assert "alsa-ucm-conf" not in data["packages"]


def test_hcl_matches_family_wildcards_and_reports_hardware_classes(tmp_path: Path) -> None:
    env = make_fake_machine(tmp_path, "LENOVO", "ThinkPad T14 Gen 5")
    write(
        tmp_path / "cpuinfo",
        "vendor_id : GenuineIntel\n"
        "model name : Intel Core Ultra 7 155H\n"
        "processor : 0\n"
        "processor : 1\n",
    )
    env["GRINTION_CPUINFO"] = str(tmp_path / "cpuinfo")
    env["GRINTION_HCL_DB"] = str(HCL_DB)
    result = run_bin("grintion-hcl", "--json", env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["platform"]["profile"] == "lenovo"
    assert data["platform"]["family"] == "ThinkPad"
    assert data["system"]["family"] == "ThinkPad"
    assert data["compatibility"] in {"compatible", "verified"}
    assert data["features"]["wifi"] is True
    assert data["features"]["audio"] is True
    assert data["features"]["ports"] is True
    assert data["features"]["storage"] is False
    assert data["features"]["ethernet"] is False
    wifi = next(dev for dev in data["pci_devices"] if dev["device_id"] == "8086:a0f0")
    assert wifi["status"] == "compatible"
    usb = next(dev for dev in data["pci_devices"] if dev["device_id"] == "8086:a0ed")
    assert usb["status"] == "compatible"


def test_kernel_contract_contains_laptop_hardware_drivers() -> None:
    text = (REPO_ROOT / "config" / "kernel-hardened.config").read_text(encoding="utf-8")
    required = [
        "CONFIG_BLK_DEV_NVME=y",
        "CONFIG_MMC=m",
        "CONFIG_MMC_SDHCI_PCI=m",
        "CONFIG_MISC_RTSX_PCI=m",
        "CONFIG_SCSI_UFSHCD=m",
        "CONFIG_USB4=m",
        "CONFIG_USB4_NET=m",
        "CONFIG_TYPEC_UCSI=m",
        "CONFIG_TYPEC_DP_ALTMODE=m",
        "CONFIG_RTW89_8852BE=m",
        "CONFIG_RTW89_8922AE=m",
        "CONFIG_MT7925E=m",
        "CONFIG_ATH9K=m",
        "CONFIG_BRCMFMAC_PCIE=y",
        "CONFIG_SND_SOC_SOF_ALDERLAKE=m",
        "CONFIG_SND_SOC_SOF_METEORLAKE=m",
        "CONFIG_SND_SOC_SOF_HDA_AUDIO_CODEC=y",
        "CONFIG_SOUNDWIRE_INTEL=m",
        "CONFIG_SND_SOC_AMD_ACP6x=m",
        "CONFIG_THINKPAD_ACPI=m",
        "CONFIG_THINKPAD_LMI=m",
        "CONFIG_IDEAPAD_LAPTOP=m",
        "CONFIG_DELL_LAPTOP=m",
        "CONFIG_DELL_WMI=m",
        "CONFIG_DELL_SMBIOS=m",
        "CONFIG_DELL_RBU=n",
        "CONFIG_HP_WMI=m",
        "CONFIG_HP_ACCEL=m",
        "CONFIG_ACER_WMI=m",
        "CONFIG_ASUS_WMI=m",
        "CONFIG_MSI_EC=m",
        "CONFIG_MSI_WMI_PLATFORM=m",
        "CONFIG_SAMSUNG_LAPTOP=m",
        "CONFIG_INTEL_PMC_CORE=m",
        "CONFIG_I2C_HID=y",
        "CONFIG_PINCTRL_INTEL=m",
        "CONFIG_BT_HCIBTUSB=m",
        "CONFIG_IGC=m",
        "CONFIG_FW_LOADER_USER_HELPER=n",
    ]
    for line in required:
        assert line in text, line


def test_static_gate_runs_the_laptop_matrix_tests() -> None:
    check = (REPO_ROOT / "build" / "check.sh").read_text(encoding="utf-8")
    assert "tests/test_laptop_hardware_support.py" in check
