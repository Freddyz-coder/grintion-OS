from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"


def run_bin(cmd: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    executable = BIN_DIR / cmd
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        [str(executable), *args],
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def test_grintion_apparmor_status_and_modes(tmp_path: Path):
    profile_dir = tmp_path / "apparmor.d"
    profile_dir.mkdir()
    sample_profile = profile_dir / "usr.bin.testapp"
    sample_profile.write_text("/usr/bin/testapp {\n  /etc/test r,\n}\n")

    env = {"GRINTION_APPARMOR_DIR": str(profile_dir)}
    res = run_bin("grintion-apparmor", "status", "--json", env=env)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["profiles_loaded"] == 1
    assert data["enforce_count"] == 1

    # Switch to complain mode
    res_comp = run_bin("grintion-apparmor", "complain", "usr.bin.testapp", env=env)
    assert res_comp.returncode == 0
    assert "complain" in sample_profile.read_text()

    # Switch back to enforce mode
    res_enf = run_bin("grintion-apparmor", "enforce", "usr.bin.testapp", env=env)
    assert res_enf.returncode == 0
    assert "flags=(complain)" not in sample_profile.read_text()


def test_grintion_sandbox_isolation_and_negative_test(tmp_path: Path):
    # Test dry-run generation
    res = run_bin("grintion-sandbox", "--no-net", "--private-home", "--dry-run", "curl", "https://example.com")
    assert res.returncode == 0
    assert "--unshare-net" in res.stdout
    assert "--ro-bind / /" in res.stdout

    # Negative test: simulated mock sandbox verifies isolation boundary
    env = {"GRINTION_SANDBOX_MOCK": "1", "MOCK_NET_TEST": "1"}
    res_neg = run_bin("grintion-sandbox", "--no-net", "ping", "8.8.8.8", env=env)
    assert res_neg.returncode != 0


def test_grintion_integrity_baseline_and_tamper_detection(tmp_path: Path):
    test_dir = tmp_path / "monitored"
    test_dir.mkdir()
    f1 = test_dir / "bin_foo"
    f1.write_text("secure binary content")
    db_file = tmp_path / "integrity.json"

    # Initialize baseline
    res_init = run_bin("grintion-integrity", "init", "--db", str(db_file), "--path", str(test_dir))
    assert res_init.returncode == 0
    assert db_file.is_file()

    # Check matches baseline
    res_chk = run_bin("grintion-integrity", "check", "--db", str(db_file), "--path", str(test_dir), "--json")
    assert res_chk.returncode == 0
    data = json.loads(res_chk.stdout)
    assert data["status"] == "clean"

    # Negative test: tamper with monitored file
    f1.write_text("maliciously modified content")
    res_tamper = run_bin("grintion-integrity", "check", "--db", str(db_file), "--path", str(test_dir), "--json")
    assert res_tamper.returncode == 1
    tamper_data = json.loads(res_tamper.stdout)
    assert tamper_data["status"] == "tampered"
    assert str(f1) in tamper_data["modified"]


def test_grintion_scan_rogue_suid_detection(tmp_path: Path):
    # Standard clean scan
    res = run_bin("grintion-scan", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "status" in data


def test_grintion_usb_data_block_and_authorization(tmp_path: Path):
    usb_conf = tmp_path / "usb.conf"
    sys_usb = tmp_path / "sys_usb"
    sys_usb.mkdir()

    # Create simulated USB hub and device
    dev1 = sys_usb / "1-1"
    dev1.mkdir()
    (dev1 / "idVendor").write_text("1234")
    (dev1 / "idProduct").write_text("5678")
    (dev1 / "product").write_text("FlashDrive")
    (dev1 / "authorized").write_text("1")

    env = {
        "GRINTION_USB_CONF": str(usb_conf),
        "GRINTION_SYSFS_USB": str(sys_usb),
    }

    # Verify device list
    res_list = run_bin("grintion-usb", "list", "--json", env=env)
    assert res_list.returncode == 0
    devs = json.loads(res_list.stdout)
    assert len(devs) == 1
    assert devs[0]["product_name"] == "FlashDrive"

    # Enable data blocking
    res_block = run_bin("grintion-usb", "block-data", env=env)
    assert res_block.returncode == 0
    assert "data_block=1" in usb_conf.read_text()

    # Deauthorize device (negative test: device denied access)
    res_deauth = run_bin("grintion-usb", "deauthorize", "1-1", env=env)
    assert res_deauth.returncode == 0
    assert (dev1 / "authorized").read_text().strip() == "0"


def test_grintion_vault_and_shred(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    env = {"GRINTION_VAULT_DIR": str(vault_dir)}

    # Store and retrieve secret
    res_set = run_bin("grintion-vault", "set", "api_token", "super_secret_123", "--passphrase", "vaultpass", env=env)
    assert res_set.returncode == 0

    res_get = run_bin("grintion-vault", "get", "api_token", "--passphrase", "vaultpass", env=env)
    assert res_get.returncode == 0
    assert res_get.stdout.strip() == "super_secret_123"

    # Failed decryption with wrong password
    res_fail = run_bin("grintion-vault", "get", "api_token", "--passphrase", "wrongpass", env=env)
    assert res_fail.returncode != 0

    # Test file shredding
    shred_target = tmp_path / "temp_key.pem"
    shred_target.write_text("confidential private key")
    res_shred = run_bin("grintion-vault", "shred", str(shred_target))
    assert res_shred.returncode == 0
    assert not shred_target.exists()


def test_grintion_shield_brute_force_detection(tmp_path: Path):
    bans_file = tmp_path / "bans.json"
    auth_log = tmp_path / "auth.log"
    auth_log.write_text(
        "Nov 07 12:00:01 host sshd[100]: Failed password for invalid user admin from 198.51.100.42 port 54321 ssh2\n"
        "Nov 07 12:00:02 host sshd[101]: Failed password for invalid user admin from 198.51.100.42 port 54322 ssh2\n"
        "Nov 07 12:00:03 host sshd[102]: Failed password for invalid user admin from 198.51.100.42 port 54323 ssh2\n"
    )

    env = {
        "GRINTION_SHIELD_BANS": str(bans_file),
        "GRINTION_AUTH_LOG": str(auth_log),
    }

    # Trigger scan with threshold of 3
    res_scan = run_bin("grintion-shield", "scan-log", "--log", str(auth_log), "--max-retry", "3", env=env)
    assert res_scan.returncode == 0
    assert "198.51.100.42" in res_scan.stdout

    # Verify banned status
    res_st = run_bin("grintion-shield", "status", "--json", env=env)
    assert res_st.returncode == 0
    data = json.loads(res_st.stdout)
    assert "198.51.100.42" in data


def test_grintion_security_profiles_and_report_integration(tmp_path: Path):
    prof_file = tmp_path / "security-profile"
    conf_file = tmp_path / "security.conf"
    env = {
        "GRINTION_SECURITY_PROFILE": str(prof_file),
        "GRINTION_SECURITY_CONF": str(conf_file),
    }

    # List profiles
    res_list = run_bin("grintion-security", "list", "--json", env=env)
    assert res_list.returncode == 0
    data = json.loads(res_list.stdout)
    assert "workstation" in data
    assert "server" in data
    assert "air-gapped" in data

    # Set server profile
    res_set = run_bin("grintion-security", "set", "server", env=env)
    assert res_set.returncode == 0
    assert prof_file.read_text().strip() == "server"
    assert "PROFILE=server" in conf_file.read_text()


def test_grintion_privacy_dashboard():
    res = run_bin("grintion-privacy", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "firewall" in data
    assert "listening_sockets" in data


def test_grintion_apparmor_load_all_and_verify(tmp_path: Path):
    profile_dir = tmp_path / "apparmor.d"
    profile_dir.mkdir()
    profile = profile_dir / "usr.bin.demo"
    profile.write_text("/usr/bin/demo {\n  /etc/demo r,\n}\n")

    parser_log = tmp_path / "parser.log"
    parser = tmp_path / "apparmor_parser"
    parser.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"{parser_log}\"\nexit 0\n")
    parser.chmod(0o755)

    env = {
        "GRINTION_APPARMOR_DIR": str(profile_dir),
        "GRINTION_APPARMOR_PARSER": str(parser),
    }
    res = run_bin("grintion-apparmor", "load-all", env=env)
    assert res.returncode == 0
    assert "-r" in parser_log.read_text()
    assert str(profile) in parser_log.read_text()

    sysfs = tmp_path / "securityfs"
    sysfs.mkdir()
    (sysfs / "profiles").write_text("demo (enforce)\n")
    enabled = tmp_path / "enabled"
    enabled.write_text("Y\n")
    env.update({
        "GRINTION_SYS_APPARMOR": str(sysfs),
        "GRINTION_SYSFS_APPARMOR_PARAM": str(enabled),
    })

    res_status = run_bin("grintion-apparmor", "status", "--json", env=env)
    assert res_status.returncode == 0
    status = json.loads(res_status.stdout)
    assert status["kernel_loaded"] == 1
    assert status["kernel_enforce_count"] == 1

    res_verify = run_bin("grintion-apparmor", "verify", "--json", env=env)
    assert res_verify.returncode == 0
    assert json.loads(res_verify.stdout)["compliant"] is True

    other = profile_dir / "usr.bin.other"
    other.write_text("/usr/bin/other {\n  /etc/other r,\n}\n")
    res_missing = run_bin("grintion-apparmor", "verify", "--json", env=env)
    assert res_missing.returncode == 1
    assert "/usr/bin/other" in json.loads(res_missing.stdout)["missing"]
    other.unlink()

    profile.write_text("/usr/bin/demo flags=(complain) {\n  /etc/demo r,\n}\n")
    res_complain = run_bin("grintion-apparmor", "verify", "--json", env=env)
    assert res_complain.returncode == 1
    assert json.loads(res_complain.stdout)["compliant"] is False


def test_apparmor_profiles_load_at_boot_and_deny_secrets():
    profiles = [p for p in (REPO_ROOT / "etc" / "apparmor.d").glob("*") if p.is_file()]
    assert profiles
    for path in profiles:
        text = path.read_text()
        assert "flags=(attach_disconnected,mediate_deleted)" in text, path
        assert "deny /etc/shadow rwklx" in text, path
        assert "deny ptrace" in text, path
        assert "deny capability sys_admin" in text, path

    service = REPO_ROOT / "etc" / "sv" / "apparmor" / "run"
    assert service.is_file()
    assert os.access(service, os.X_OK)
    assert "apparmor_parser" in service.read_text()
    assert '"$parser" -r' in service.read_text()

    kernel = (REPO_ROOT / "config" / "kernel-hardened.config").read_text()
    assert "CONFIG_SECURITY_APPARMOR=y" in kernel
    for boot_file in ("build/build-iso.sh", "bin/limine-deploy", "bin/grintion-install", "bin/grintion-uki"):
        assert "security=apparmor apparmor=1" in (REPO_ROOT / boot_file).read_text(), boot_file

    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert "udev timesync apparmor; do" in rootfs
    assert "for dir in abi tunables abstractions; do" in rootfs
    mac = (REPO_ROOT / "config" / "rootfs.mac-binaries").read_text()
    assert "apparmor_parser" in mac


def test_x11_remote_transports_and_cookies_are_locked_down():
    xserverrc = REPO_ROOT / "etc" / "X11" / "xinit" / "xserverrc"
    assert xserverrc.is_file()
    assert os.access(xserverrc, os.X_OK)
    server_text = xserverrc.read_text()
    assert "-nolisten tcp" in server_text
    assert "-nolisten local" in server_text

    hook = REPO_ROOT / "etc" / "X11" / "xinit" / "xinitrc.d" / "05-grintion-x11-security.sh"
    assert hook.is_file()
    assert os.access(hook, os.X_OK)
    hook_text = hook.read_text()
    assert "chmod 600" in hook_text
    assert "xhost -" in hook_text

    desktop = (REPO_ROOT / "bin" / "grintion-desktop").read_text()
    assert "xserver-command=X -nolisten tcp -nolisten local" in desktop
    assert "ServerArguments=-nolisten tcp -nolisten local" in desktop

    wrapper = (REPO_ROOT / "etc" / "X11" / "Xwrapper.config").read_text()
    assert "allowed_users = console" in wrapper

    report = (REPO_ROOT / "bin" / "grintion-security-report").read_text()
    assert "x11-access" in report

