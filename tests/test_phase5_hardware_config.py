from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HCL = REPO_ROOT / "bin" / "grintion-hcl"
CONFIG = REPO_ROOT / "bin" / "grintion-config"
DOCTOR = REPO_ROOT / "bin" / "grintion-doctor"
WATCHDOG = REPO_ROOT / "bin" / "grintion-watchdog"
POWER = REPO_ROOT / "bin" / "grintion-power"
NETWORK = REPO_ROOT / "bin" / "grintion-network"
CGROUP = REPO_ROOT / "bin" / "grintion-cgroup"


def test_grintion_hcl_identifies_machine_json() -> None:
    res = subprocess.run([str(HCL), "--json"], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert "machine" in data
    assert "compatibility" in data
    assert data["compatibility"] in {"verified", "compatible", "untested", "incompatible"}
    assert "cpu" in data
    assert data["cpu"]["cores"] >= 1
    assert "pci_devices" in data
    assert isinstance(data["pci_devices"], list)


def test_grintion_hcl_custom_database(tmp_path: Path) -> None:
    custom_db = tmp_path / "custom_hcl.json"
    custom_db.write_text(json.dumps({
        "version": 1,
        "vendors": {
            "system": [{"vendor": "TestVendor", "product": "TestModel", "status": "verified"}],
            "cpu": [{"vendor": "TestCPU", "family": "x86_64", "status": "verified"}],
            "pci": [{"device_id": "1234:5678", "name": "Test NIC", "status": "verified"}],
        }
    }))
    dmi_dir = tmp_path / "dmi"
    dmi_dir.mkdir()
    (dmi_dir / "sys_vendor").write_text("TestVendor\n")
    (dmi_dir / "product_name").write_text("TestModel\n")
    (dmi_dir / "board_name").write_text("TestBoard\n")

    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("vendor_id : TestCPU\nmodel name : Test Core i9\nprocessor : 0\nprocessor : 1\n")

    env = os.environ.copy()
    env["GRINTION_HCL_DB"] = str(custom_db)
    env["GRINTION_SYSFS_DMI"] = str(dmi_dir)
    env["GRINTION_CPUINFO"] = str(cpuinfo)

    res = subprocess.run([str(HCL), "--json"], capture_output=True, text=True, check=False, env=env)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["machine"] == "TestVendor TestModel"
    assert data["system"]["status"] == "verified"
    assert data["compatibility"] == "verified"
    assert data["cpu"]["cores"] == 2


def test_grintion_config_changes_survive_reboot(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # Set timezone
    r1 = subprocess.run([str(CONFIG), "set", "timezone", "Europe/London"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    assert (tmp_path / "etc" / "timezone").read_text().strip() == "Europe/London"

    # Set locale
    r2 = subprocess.run([str(CONFIG), "set", "locale", "en_GB.UTF-8"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    assert "LANG=en_GB.UTF-8" in (tmp_path / "etc" / "locale.conf").read_text()

    # Set keyboard
    r3 = subprocess.run([str(CONFIG), "set", "keyboard", "uk"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    assert "KEYMAP=uk" in (tmp_path / "etc" / "vconsole.conf").read_text()

    # Set hostname
    r4 = subprocess.run([str(CONFIG), "set", "hostname", "grintion-testbox"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 0
    assert (tmp_path / "etc" / "hostname").read_text().strip() == "grintion-testbox"

    # Verify show --json reflects all persisted changes
    r5 = subprocess.run([str(CONFIG), "show", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r5.returncode == 0
    data = json.loads(r5.stdout)
    assert data["timezone"] == "Europe/London"
    assert data["locale"] == "en_GB.UTF-8"
    assert data["keymap"] == "uk"
    assert data["hostname"] == "grintion-testbox"


def test_grintion_config_services_and_power(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # Setup mock service
    sv_dir = tmp_path / "etc" / "sv" / "test-svc"
    sv_dir.mkdir(parents=True)
    (sv_dir / "run").write_text("#!/bin/sh\nexec sleep 100\n")

    # Enable service
    r1 = subprocess.run([str(CONFIG), "service", "enable", "test-svc"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    assert (tmp_path / "var" / "service" / "test-svc").is_symlink()

    # List services
    r2 = subprocess.run([str(CONFIG), "service", "list", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    svcs = json.loads(r2.stdout)
    assert any(s["name"] == "test-svc" and s["enabled"] for s in svcs)

    # Disable service
    r3 = subprocess.run([str(CONFIG), "service", "disable", "test-svc"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    assert not (tmp_path / "var" / "service" / "test-svc").exists()

    # Set power governor
    r4 = subprocess.run([str(CONFIG), "power", "governor", "powersave"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 0
    power_conf = (tmp_path / "etc" / "grintion" / "power.conf").read_text()
    assert "governor = powersave" in power_conf


def test_grintion_doctor_fix_repairs_system_state(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)

    # 1. Broken tmp permissions (0755 instead of 1777)
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    tmp_dir.chmod(0o755)

    # 2. Stale garb lock file with dead PID
    garb_dir = tmp_path / "var" / "lib" / "garb"
    garb_dir.mkdir(parents=True)
    lock_file = garb_dir / "lock"
    lock_file.write_text("999999\n")

    # 3. Dangling service link
    service_dir = tmp_path / "var" / "service"
    service_dir.mkdir(parents=True)
    dangling = service_dir / "dead-service"
    dangling.symlink_to(tmp_path / "non-existent")

    # 4. Missing resolv.conf
    resolv_file = tmp_path / "etc" / "resolv.conf"
    if resolv_file.exists():
        resolv_file.unlink()

    # Run doctor --fix
    res = subprocess.run([str(DOCTOR), "--fix"], capture_output=True, text=True, check=False, env=env)
    assert res.returncode == 0
    assert "[FIXED]" in res.stdout

    # Verify repairs
    assert (tmp_dir.stat().st_mode & 0o7777) == 0o1777
    assert not lock_file.exists()
    assert not dangling.is_symlink()
    assert resolv_file.is_file()
    assert "nameserver" in resolv_file.read_text()

    # Verify fix audit log was recorded
    fix_log = tmp_path / "var" / "log" / "grintion-doctor-fix.json"
    assert fix_log.is_file()
    assert "fixes_applied" in fix_log.read_text()


def test_grintion_watchdog_restarts_killed_service(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)
    env["GRINTION_WATCHDOG_MOCK_STATUS"] = "udev=down,dbus=up,network=up"
    env["GRINTION_WATCHDOG_MOCK_RESTART"] = "1"

    conf = tmp_path / "etc" / "grintion" / "watchdog.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text("SERVICES = udev, dbus, network\nMAX_RESTARTS = 3\nWINDOW_SECONDS = 60\n")

    # Check restarts down service
    res1 = subprocess.run([str(WATCHDOG), "check"], capture_output=True, text=True, check=False, env=env)
    assert res1.returncode == 0
    assert "[WATCHDOG] service 'udev' was down; restarted successfully" in res1.stdout

    # Check status reports restart count
    res2 = subprocess.run([str(WATCHDOG), "status", "--json"], capture_output=True, text=True, check=False, env=env)
    assert res2.returncode == 0
    status = json.loads(res2.stdout)
    udev_info = next(s for s in status if s["service"] == "udev")
    assert udev_info["restarts_in_window"] == 1
    assert not udev_info["degraded"]

    # Trigger multiple failures exceeding threshold
    subprocess.run([str(WATCHDOG), "check"], capture_output=True, text=True, check=False, env=env)
    subprocess.run([str(WATCHDOG), "check"], capture_output=True, text=True, check=False, env=env)
    res_limit = subprocess.run([str(WATCHDOG), "check"], capture_output=True, text=True, check=False, env=env)
    assert res_limit.returncode == 2
    assert "marked DEGRADED" in res_limit.stderr

    # Verify alert logged
    alert_log = tmp_path / "var" / "log" / "grintion-watchdog.log"
    assert alert_log.is_file()
    assert "marked DEGRADED" in alert_log.read_text()


def test_grintion_power_management(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_ROOT"] = str(tmp_path)
    env["GRINTION_POWER_CONF"] = str(tmp_path / "etc" / "grintion" / "power.conf")

    # Set governor
    r1 = subprocess.run([str(POWER), "set-governor", "powersave"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0

    # Set thermal profile
    r2 = subprocess.run([str(POWER), "set-thermal", "quiet"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0

    # Set charge limit
    r3 = subprocess.run([str(POWER), "set-charge-limit", "80"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0

    # Set lid action
    r4 = subprocess.run([str(POWER), "set-lid-action", "ignore"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 0

    # Query status
    r5 = subprocess.run([str(POWER), "status", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r5.returncode == 0
    info = json.loads(r5.stdout)
    assert info["governor"] == "powersave"
    assert info["thermal_profile"] == "quiet"
    assert info["charge_threshold"] == 80
    assert info["lid_action"] == "ignore"


def test_grintion_network_wifi_roaming_priority(tmp_path: Path) -> None:
    conf = tmp_path / "network.conf"
    env = os.environ.copy()
    env["GRINTION_NETWORK_CONF"] = str(conf)
    env["GRINTION_NETWORK_LIB"] = str(REPO_ROOT / "etc" / "grintion" / "network.lib.sh")

    # Save two networks: AP1 (priority 10) and AP2 (priority 50)
    r1 = subprocess.run([str(NETWORK), "--no-apply", "save-network", "AP1", "pass1", "--priority", "10"], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    r2 = subprocess.run([str(NETWORK), "--no-apply", "save-network", "AP2", "pass2", "--priority", "50"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0

    # Check saved-networks --json
    r3 = subprocess.run([str(NETWORK), "saved-networks", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    saved = json.loads(r3.stdout)
    assert len(saved) == 2

    # Mock visible APs: both AP1 and AP2 are visible
    env["GRINTION_WIFI_SCAN_MOCK"] = "AP1,AP2,OtherPublic"
    r4 = subprocess.run([str(NETWORK), "--no-apply", "roam"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 0
    assert "roaming from '' to higher-priority network 'AP2' (priority 50)" in r4.stdout
    assert "ssid = AP2" in conf.read_text()

    # Now AP2 disappears, only AP1 is in range
    env["GRINTION_WIFI_SCAN_MOCK"] = "AP1,OtherPublic"
    r5 = subprocess.run([str(NETWORK), "--no-apply", "roam"], capture_output=True, text=True, check=False, env=env)
    assert r5.returncode == 0
    assert "roaming from 'AP2' to higher-priority network 'AP1' (priority 10)" in r5.stdout
    assert "ssid = AP1" in conf.read_text()


def test_grintion_network_enterprise_and_privacy(tmp_path: Path) -> None:
    conf = tmp_path / "network.conf"
    env = os.environ.copy()
    env["GRINTION_NETWORK_CONF"] = str(conf)
    env["GRINTION_NETWORK_LIB"] = str(REPO_ROOT / "etc" / "grintion" / "network.lib.sh")

    # WPA-Enterprise
    r1 = subprocess.run([
        str(NETWORK), "--no-apply", "connect-enterprise", "CorpNet",
        "--identity", "employee42", "--password", "secretCorpPass",
        "--eap-method", "PEAP"
    ], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0
    content = conf.read_text()
    assert "enterprise = 1" in content
    assert "identity = employee42" in content

    # MAC randomization
    r2 = subprocess.run([str(NETWORK), "--no-apply", "set-mac-randomization", "wlan0", "enable"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    assert "mac_randomize = true" in conf.read_text()

    # Metered connection
    r3 = subprocess.run([str(NETWORK), "--no-apply", "set-metered", "wlan0", "yes"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0
    assert "metered = true" in conf.read_text()

    # Profile save and apply
    r4 = subprocess.run([str(NETWORK), "--no-apply", "profile", "save", "work"], capture_output=True, text=True, check=False, env=env)
    assert r4.returncode == 0
    assert (tmp_path / "profiles.d" / "network-work.conf").is_file()

    # DNS leak test
    env["GRINTION_DNS_LEAK_MOCK"] = "false"
    resolv = tmp_path / "etc" / "resolv.conf"
    resolv.parent.mkdir(parents=True)
    resolv.write_text("nameserver 1.1.1.1\n")
    # Point test to resolv
    r5 = subprocess.run([str(NETWORK), "dns-leak-test", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r5.returncode == 0
    leak_data = json.loads(r5.stdout)
    assert leak_data["dns_leak_detected"] is False


def test_grintion_cgroup_limits(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GRINTION_CGROUP_ROOT"] = str(tmp_path / "sys" / "fs" / "cgroup" / "grintion")

    # Apply limits
    r1 = subprocess.run([
        str(CGROUP), "apply", "desktop-session",
        "--memory", "2G", "--cpu", "100000 100000", "--pids", "500"
    ], capture_output=True, text=True, check=False, env=env)
    assert r1.returncode == 0

    # Query status
    r2 = subprocess.run([str(CGROUP), "status", "--json"], capture_output=True, text=True, check=False, env=env)
    assert r2.returncode == 0
    info = json.loads(r2.stdout)
    slice_info = next(s for s in info["slices"] if s["service"] == "desktop-session")
    assert slice_info["memory_max"] == "2G"
    assert slice_info["cpu_max"] == "100000 100000"
    assert slice_info["pids_max"] == "500"

    # Test wait-for
    env["GRINTION_SERVICE_ACTIVE_MOCK"] = "1"
    r3 = subprocess.run([str(CGROUP), "wait-for", "dbus", "--timeout", "2"], capture_output=True, text=True, check=False, env=env)
    assert r3.returncode == 0

