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
    if not executable.exists():
        clean = cmd.removeprefix("grintion-")
        alt = BIN_DIR / clean
        if alt.exists():
            executable = alt
        else:
            alt2 = BIN_DIR / f"grintion-{clean}"
            if alt2.exists():
                executable = alt2
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

    # Restore the contents, then add setuid. A hash-only checker would call
    # this clean; the mode-aware baseline must flag the privilege change.
    f1.write_text("secure binary content")
    f1.chmod(0o4755)
    res_mode = run_bin(
        "grintion-integrity", "check", "--db", str(db_file), "--path", str(test_dir), "--json"
    )
    assert res_mode.returncode == 1
    mode_data = json.loads(res_mode.stdout)
    assert str(f1) in mode_data["mode_changed"]
    assert str(f1) in mode_data["privilege_changed"]


def test_grintion_scan_rogue_suid_detection(tmp_path: Path):
    # Point the scan at a controlled path so host temporary directories do not
    # change the result, and verify it actually finds a setuid file.
    rogue_dir = tmp_path / "rogue"
    rogue_dir.mkdir()
    rogue = rogue_dir / "suid-helper"
    rogue.write_text("#!/bin/sh\n")
    rogue.chmod(0o4755)

    res = run_bin(
        "grintion-scan", "--json", env={"GRINTION_SCAN_PATHS": str(rogue_dir)}
    )
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert str(rogue) in data["rogue_suid"]

    # A host interface can legitimately be in promiscuous mode (for example a
    # container veth). The clean-path assertion checks report consistency, not
    # the host's network state.
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    res = run_bin(
        "grintion-scan", "--json", env={"GRINTION_SCAN_PATHS": str(empty_dir)}
    )
    data = json.loads(res.stdout)
    assert data["rogue_suid"] == []
    host_findings = bool(data["promiscuous_interfaces"] or data["hidden_suspicious_files"])
    assert res.returncode == (1 if host_findings else 0)


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
        "GRINTION_USB_CONF": str(tmp_path / "usb.conf"),
        "GRINTION_FIREWALL_FILE": str(tmp_path / "firewall.nft"),
        "GRINTION_SERVICE_DIR": str(tmp_path / "service"),
        "GRINTION_AUDITD_BIN": "/bin/true",
    }

    # List profiles
    res_list = run_bin("grintion-security", "list", "--json", env=env)
    assert res_list.returncode == 0
    data = json.loads(res_list.stdout)
    assert "workstation" in data
    assert "server" in data
    assert "air-gapped" in data

    # Set server profile without assuming the test host can load nftables or
    # AppArmor; the full apply path is covered separately with fake tools.
    res_set = run_bin("grintion-security", "set", "server", "--config-only", env=env)
    assert res_set.returncode == 0
    assert "configuration written" in res_set.stdout
    assert prof_file.read_text().strip() == "server"
    assert "PROFILE=server" in conf_file.read_text()
    assert "USB_DATA_BLOCK=1" in conf_file.read_text()

    # Staging an air-gapped image records the policy but does not create a
    # live service link without a booting target.
    res_air = run_bin("grintion-security", "set", "air-gapped", "--config-only", env=env)
    assert res_air.returncode == 0
    assert prof_file.read_text().strip() == "air-gapped"
    assert "ALLOW_NETWORK=0" in conf_file.read_text()
    assert "FIREWALL_POLICY=drop_all" in conf_file.read_text()
    assert not (tmp_path / "service" / "airgap").exists()


def test_grintion_security_applies_and_verifies_controls(tmp_path: Path):
    prof_file = tmp_path / "security-profile"
    conf_file = tmp_path / "security.conf"
    usb_conf = tmp_path / "usb.conf"
    firewall_file = tmp_path / "firewall.nft"

    nft = tmp_path / "nft"
    nft.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "list" ]; then\n'
        '  echo "chain input_grintion_strict_drop {"\n'
        "  exit 0\n"
        "fi\n"
        "cat >/dev/null\n"
        "exit 0\n"
    )
    nft.chmod(0o755)
    apparmor = tmp_path / "apparmor"
    apparmor.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "verify" ]; then\n'
        "  echo '{\"compliant\": true, \"kernel_enforce\": 7, \"issues\": []}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    apparmor.chmod(0o755)
    usb = tmp_path / "usb"
    usb.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" > \"$GRINTION_USB_LOG\"\n"
        "[ \"$1\" = block-data ] && printf 'data_block=1\\n' > \"$GRINTION_USB_CONF\"\n"
        "exit 0\n"
    )
    usb.chmod(0o755)

    env = {
        "GRINTION_SECURITY_PROFILE": str(prof_file),
        "GRINTION_SECURITY_CONF": str(conf_file),
        "GRINTION_USB_CONF": str(usb_conf),
        "GRINTION_FIREWALL_FILE": str(firewall_file),
        "GRINTION_SERVICE_DIR": str(tmp_path / "service"),
        "GRINTION_NFT_BIN": str(nft),
        "GRINTION_APPARMOR_BIN": str(apparmor),
        "GRINTION_USB_BIN": str(usb),
        "GRINTION_USB_LOG": str(tmp_path / "usb.log"),
        "GRINTION_AUDITD_BIN": "/nonexistent/auditd",
    }
    res = run_bin("grintion-security", "set", "server", env=env)
    assert res.returncode == 0, res.stderr
    assert "applied and verified" in res.stdout
    assert "input_grintion_strict_drop" in firewall_file.read_text()
    assert (tmp_path / "usb.log").read_text().strip() == "block-data"
    assert prof_file.read_text().strip() == "server"


def test_air_gap_profile_locks_down_network_and_rolls_back(tmp_path: Path):
    prof_file = tmp_path / "security-profile"
    conf_file = tmp_path / "security.conf"
    usb_conf = tmp_path / "usb.conf"
    firewall_file = tmp_path / "firewall.nft"
    nft_state = tmp_path / "nft.state"
    sv_log = tmp_path / "sv.log"
    rfkill_log = tmp_path / "rfkill.log"
    airgap_status = tmp_path / "run" / "airgap"
    service_dir = tmp_path / "service"
    service_dir.mkdir()

    nft = tmp_path / "nft"
    nft.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "list" ]; then\n'
        f'  cat "{nft_state}" 2>/dev/null\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "-f" ]; then\n'
        f'  cat > "{nft_state}"\n'
        "  exit 0\n"
        "fi\n"
        "cat >/dev/null\n"
        "exit 0\n"
    )
    nft.chmod(0o755)

    apparmor = tmp_path / "apparmor"
    apparmor.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "verify" ]; then\n'
        "  echo '{\"compliant\": true, \"kernel_enforce\": 7, \"issues\": []}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    apparmor.chmod(0o755)

    usb = tmp_path / "usb"
    usb.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = block-data ]; then printf 'data_block=1\\n' > \"$GRINTION_USB_CONF\"; fi\n"
        "if [ \"$1\" = allow-data ]; then printf 'data_block=0\\n' > \"$GRINTION_USB_CONF\"; fi\n"
        "exit 0\n"
    )
    usb.chmod(0o755)

    sv = tmp_path / "sv"
    sv.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{sv_log}"\n'
        'if [ "$1" = "up" ] && [ "$2" = "airgap" ]; then\n'
        f'  mkdir -p "{airgap_status.parent}"\n'
        f'  printf "active=1\\n" > "{airgap_status}"\n'
        "fi\n"
        "exit 0\n"
    )
    sv.chmod(0o755)

    ip = tmp_path / "ip"
    ip.write_text(
        "#!/bin/sh\n"
        "cat <<'EOF'\n"
        "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n"
        "2: eth0: <BROADCAST,MULTICAST> mtu 1500\n"
        "EOF\n"
    )
    ip.chmod(0o755)

    rfkill = tmp_path / "rfkill"
    rfkill.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{rfkill_log}"\n'
        "exit 0\n"
    )
    rfkill.chmod(0o755)

    env = {
        "GRINTION_SECURITY_PROFILE": str(prof_file),
        "GRINTION_SECURITY_CONF": str(conf_file),
        "GRINTION_USB_CONF": str(usb_conf),
        "GRINTION_FIREWALL_FILE": str(firewall_file),
        "GRINTION_SERVICE_DIR": str(service_dir),
        "GRINTION_AIRGAP_SERVICE": str(REPO_ROOT / "etc" / "sv" / "airgap"),
        "GRINTION_AIRGAP_STATUS": str(airgap_status),
        "GRINTION_AIRGAP_RFKILL": str(tmp_path / "rfkill.state"),
        "GRINTION_NFT_BIN": str(nft),
        "GRINTION_APPARMOR_BIN": str(apparmor),
        "GRINTION_USB_BIN": str(usb),
        "GRINTION_SV_BIN": str(sv),
        "GRINTION_IP_BIN": str(ip),
        "GRINTION_RFKILL_BIN": str(rfkill),
        "GRINTION_AUDITD_BIN": "/nonexistent/auditd",
    }

    res = run_bin("grintion-security", "set", "air-gapped", env=env)
    assert res.returncode == 0, res.stderr
    assert "applied and verified" in res.stdout
    assert prof_file.read_text().strip() == "air-gapped"
    assert "ALLOW_NETWORK=0" in conf_file.read_text()
    assert (service_dir / "airgap").is_symlink()
    assert airgap_status.is_file()
    log = sv_log.read_text()
    assert "up airgap" in log
    assert "down network" in log
    assert "chain input_grintion_drop_all" in firewall_file.read_text()
    assert "policy drop;" in nft_state.read_text()
    assert "data_block=1" in usb_conf.read_text()

    # A live interface that comes back up must fail verification, even though
    # the ruleset and the service state are otherwise correct.
    ip.write_text(
        "#!/bin/sh\n"
        "cat <<'EOF'\n"
        "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n"
        "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n"
        "EOF\n"
    )
    res_verify = run_bin("grintion-security", "verify", "--json", env=env)
    assert res_verify.returncode == 1
    checks = json.loads(res_verify.stdout)["checks"]
    assert any(
        check["item"] == "network-interfaces" and check["status"] == "fail"
        for check in checks
    )

    # Switching back stops the service and restores the network service path.
    res_back = run_bin("grintion-security", "set", "workstation", env=env)
    assert res_back.returncode == 0, res_back.stderr
    assert not (service_dir / "airgap").is_symlink()
    assert not (service_dir / "airgap").exists()
    assert not airgap_status.exists()
    assert "down airgap" in sv_log.read_text()
    assert "unblock all" in rfkill_log.read_text()

    # Re-applying the profile while an interface is still up must fail and roll
    # back to the previous networked profile instead of claiming success.
    res_fail = run_bin("grintion-security", "set", "air-gapped", env=env)
    assert res_fail.returncode != 0
    assert "was not applied" in res_fail.stderr
    assert prof_file.read_text().strip() == "workstation"
    assert not (service_dir / "airgap").is_symlink()
    assert not airgap_status.exists()

    airgap_run = REPO_ROOT / "etc" / "sv" / "airgap" / "run"
    assert airgap_run.is_file()
    assert os.access(airgap_run, os.X_OK)
    run_text = airgap_run.read_text()
    assert "rfkill block all" in run_text
    assert "ip link set" in run_text
    assert "ip addr flush" in run_text

    install_text = (REPO_ROOT / "bin" / "install").read_text()
    assert "ln -sfn /etc/sv/airgap" in install_text
    assert "ALLOW_NETWORK=$SEC_NETWORK" in install_text


def test_grintion_security_rolls_back_when_a_control_fails(tmp_path: Path):
    prof_file = tmp_path / "security-profile"
    conf_file = tmp_path / "security.conf"
    prof_file.write_text("workstation\n")
    conf_file.write_text("PROFILE=workstation\n")

    nft = tmp_path / "nft"
    nft.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-f" ]; then echo "injected failure" >&2; exit 1; fi\n'
        "cat >/dev/null\n"
        "exit 0\n"
    )
    nft.chmod(0o755)
    apparmor = tmp_path / "apparmor"
    apparmor.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "verify" ]; then echo \'{"compliant": true}\'; exit 0; fi\n'
        "exit 0\n"
    )
    apparmor.chmod(0o755)
    usb = tmp_path / "usb"
    usb.write_text("#!/bin/sh\nexit 0\n")
    usb.chmod(0o755)

    env = {
        "GRINTION_SECURITY_PROFILE": str(prof_file),
        "GRINTION_SECURITY_CONF": str(conf_file),
        "GRINTION_USB_CONF": str(tmp_path / "usb.conf"),
        "GRINTION_FIREWALL_FILE": str(tmp_path / "firewall.nft"),
        "GRINTION_SERVICE_DIR": str(tmp_path / "service"),
        "GRINTION_NFT_BIN": str(nft),
        "GRINTION_APPARMOR_BIN": str(apparmor),
        "GRINTION_USB_BIN": str(usb),
    }
    res = run_bin("grintion-security", "set", "server", env=env)
    assert res.returncode != 0
    assert "was not applied" in res.stderr
    assert prof_file.read_text().strip() == "workstation"
    assert conf_file.read_text() == "PROFILE=workstation\n"


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
    for boot_file in ("build/build-iso.sh", "bin/limine-deploy", "bin/install", "bin/uki"):
        target_path = REPO_ROOT / boot_file
        if not target_path.exists():
            target_path = REPO_ROOT / boot_file.replace("bin/", "bin/grintion-")
        assert "security=apparmor apparmor=1" in target_path.read_text(), boot_file

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

    desktop_path = BIN_DIR / "desktop" if (BIN_DIR / "desktop").exists() else BIN_DIR / "grintion-desktop"
    desktop = desktop_path.read_text()
    assert "xserver-command=X -nolisten tcp -nolisten local" in desktop
    assert "ServerArguments=-nolisten tcp -nolisten local" in desktop

    wrapper = (REPO_ROOT / "etc" / "X11" / "Xwrapper.config").read_text()
    assert "allowed_users = console" in wrapper

    report_path = BIN_DIR / "security-report" if (BIN_DIR / "security-report").exists() else BIN_DIR / "grintion-security-report"
    report = report_path.read_text()
    assert "x11-access" in report


def test_vault_path_traversal_prevention(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    outside_victim = tmp_path / "victim.txt"
    outside_victim.write_text("IMPORTANT_DATA")

    env = {"GRINTION_VAULT_DIR": str(vault_dir), "GRINTION_CERT_DIR": str(tmp_path / "certs")}
    (tmp_path / "certs").mkdir()

    # Attempt path traversal write
    res_set = run_bin("grintion-vault", "set", "../../evil", "secret_val", "--passphrase", "testpass", env=env)
    assert res_set.returncode != 0
    assert not (tmp_path / "evil.vault").exists()

    # Attempt path traversal read
    res_get = run_bin("grintion-vault", "get", "../../evil", "--passphrase", "testpass", env=env)
    assert res_get.returncode != 0

    # Attempt path traversal cert deletion
    res_untrust = run_bin("grintion-vault", "untrust-cert", "../victim.txt", env=env)
    assert res_untrust.returncode != 0
    assert outside_victim.exists()


def test_backup_verify_injection_safety(tmp_path: Path):
    target = tmp_path / "test-archive.tar.gz"
    target.write_bytes(b"dummy")
    meta = tmp_path / "test-archive.tar.gz.json"
    meta.write_text(json.dumps({"sha256": "fakehash", "path": str(target)}))

    res = run_bin("grintion-backup", "verify", str(target))
    # Should report integrity check failed, not crash or execute code
    assert res.returncode == 1
    assert "FAILED" in res.stderr or "FAILED" in res.stdout


def test_mount_and_timer_newline_rejection(tmp_path: Path):
    fstab = tmp_path / "fstab"
    fstab.write_text("# fstab\n")
    env = {"GRINTION_FSTAB": str(fstab), "GRINTION_ROOT": str(tmp_path)}

    res_mnt = run_bin(
        "grintion-mount", "add", "/dev/sda1", "/mnt/test",
        "--options", "defaults\n/dev/evil /etc ext4 defaults 0 0",
        "--no-mount",
        env=env,
    )
    assert res_mnt.returncode == 2
    assert "/dev/evil" not in fstab.read_text()

    timers_dir = tmp_path / "timers.d"
    env_timer = {
        "GRINTION_TIMERS_DIR": str(timers_dir),
        "GRINTION_SV_DIR": str(tmp_path / "sv"),
        "GRINTION_SERVICE_DIR": str(tmp_path / "service"),
        "GRINTION_ROOT": str(tmp_path),
    }
    res_timer = run_bin(
        "grintion-timer", "add", "bad_timer",
        "--schedule", "hourly",
        "--command", "echo test",
        "--description", "injected\nuser = root\ncommand = rm -rf /",
        "--disabled",
        env=env_timer,
    )
    assert res_timer.returncode == 2
    assert not (timers_dir / "bad_timer.timer").exists()


def test_shield_ip_validation_safety(tmp_path: Path):
    bans = tmp_path / "bans.json"
    env = {"GRINTION_SHIELD_BANS": str(bans)}

    res = run_bin("grintion-shield", "ban", "1.2.3.4\nALL: ALL: ALLOW", env=env)
    assert res.returncode != 0 or not bans.exists() or "ALLOW" not in bans.read_text()


def test_service_name_validation(tmp_path: Path):
    sv_dir = tmp_path / "sv"
    (sv_dir / "valid_svc").mkdir(parents=True)
    (sv_dir / "valid_svc" / "run").write_text("#!/bin/sh\n")
    env = {"GRINTION_SV_DIR": str(sv_dir), "GRINTION_SERVICE_DIR": str(tmp_path / "service")}

    # Path traversal / nested name rejected
    res_bad = run_bin("grintion-service", "status", "sub/nested", env=env)
    assert res_bad.returncode == 2

    res_flag = run_bin("grintion-service", "status", "--", "-invalid", env=env)
    assert res_flag.returncode == 2

    res_dot = run_bin("grintion-service", "status", "../traversal", env=env)
    assert res_dot.returncode == 2


def test_sandbox_empty_command():
    res = run_bin("grintion-sandbox", "--")
    assert res.returncode == 1
    assert "usage:" in res.stdout or "usage:" in res.stderr


def _write_proc_task(proc: Path, pid: int, comm: str, current: str) -> None:
    task = proc / str(pid)
    (task / "attr").mkdir(parents=True)
    (task / "fd").mkdir()
    (task / "comm").write_text(comm + "\n")
    (task / "attr" / "current").write_text(current + "\n")


def test_aa_status_reports_kernel_and_process_state(tmp_path: Path):
    secfs = tmp_path / "apparmor"
    secfs.mkdir()
    (secfs / "profiles").write_text(
        "/usr/bin/demo (enforce)\n/usr/sbin/legacy (complain)\n"
    )
    param = tmp_path / "enabled"
    param.write_text("Y\n")
    proc = tmp_path / "proc"
    proc.mkdir()
    _write_proc_task(proc, 101, "demo", "demo (enforce)")
    _write_proc_task(proc, 102, "shell", "unconfined")

    env = {
        "GRINTION_SYS_APPARMOR": str(secfs),
        "GRINTION_SYSFS_APPARMOR_PARAM": str(param),
        "GRINTION_PROC": str(proc),
    }
    res = run_bin("aa-status", "--json", env=env)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["enabled"] is True
    assert data["profiles_loaded"] == 2
    assert data["profile_modes"]["enforce"] == 1
    assert data["profile_modes"]["complain"] == 1
    assert data["processes_confined"] == 1
    assert data["processes_unconfined"] == 1

    assert run_bin("aa-status", "--enabled", env=env).returncode == 0

    # An enabled module with an unreadable profile list must not look healthy.
    (secfs / "profiles").unlink()
    missing = run_bin("aa-status", "--json", env=env)
    assert missing.returncode == 1
    assert json.loads(missing.stdout)["securityfs"] == "unreadable"


def test_aa_unconfined_reports_unconfined_socket_owners(tmp_path: Path):
    proc = tmp_path / "proc"
    proc.mkdir()
    _write_proc_task(proc, 4242, "exposed", "unconfined")
    _write_proc_task(proc, 4343, "confined", "/usr/sbin/confined (enforce)")
    _write_proc_task(proc, 4444, "established", "unconfined")

    net = proc / "net"
    net.mkdir()
    (net / "tcp").write_text(
        "  sl  local_address rem_address   st ...\n"
        "   0: 0100007F:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 12345 1\n"
        "   1: 00000000:22B8 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 23456 1\n"
        "   2: 0100007F:1F90 0100007F:C350 01 00000000:00000000 00:00000000 00000000 0 0 34567 1\n"
    )
    os.symlink("socket:[12345]", proc / "4242" / "fd" / "3")
    os.symlink("socket:[23456]", proc / "4343" / "fd" / "4")
    os.symlink("socket:[34567]", proc / "4444" / "fd" / "5")

    env = {"GRINTION_PROC": str(proc)}
    res = run_bin("aa-unconfined", "--json", env=env)
    assert res.returncode == 1, res.stderr
    data = json.loads(res.stdout)
    assert data["count"] == 1
    assert data["unconfined"][0]["pid"] == 4242
    assert data["unconfined"][0]["address"] == "127.0.0.1:22"

    paranoid = run_bin("aa-unconfined", "--json", "--paranoid", env=env)
    assert paranoid.returncode == 1
    assert {row["pid"] for row in json.loads(paranoid.stdout)["unconfined"]} == {
        4242,
        4444,
    }


def test_gzip_companions_and_version_guard_are_in_the_image():
    required = (REPO_ROOT / "config" / "rootfs.required-binaries").read_text()
    for command in (
        "gzexe",
        "zcmp",
        "zdiff",
        "zegrep",
        "zfgrep",
        "zforce",
        "zgrep",
        "zless",
        "zmore",
        "znew",
        "cmp",
    ):
        assert f"\n{command}\n" in required, command
    rootfs = (REPO_ROOT / "build" / "make-rootfs.sh").read_text()
    assert "CVE-2022-1271" in rootfs

