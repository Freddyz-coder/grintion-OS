from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "bin" / "grintion-network"
LIB = REPO_ROOT / "etc" / "grintion" / "network.lib.sh"


def run(args: list[str], config: Path, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GRINTION_NETWORK_LIB"] = str(LIB)
    result = subprocess.run(
        [str(CLI), "--config", str(config), "--no-apply", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"grintion-network {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    return result


def test_parser_reads_sections(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text(
        "[interface enp0s3]\n"
        "mode = dhcp\n"
        "\n"
        "[wifi]\n"
        "interface = wlan0\n"
        "ssid = TestNet\n"
        "psk = secret123\n"
    )
    env = os.environ.copy()
    env["GRINTION_NETWORK_CONF"] = str(config)
    result = subprocess.run(
        ["sh", "-c", '. "$1"; network_conf_get wifi ssid', "sh", str(LIB)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert result.stdout.strip() == "TestNet"


def test_set_static_writes_section(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text("# Grintion-OS network configuration\n")
    run(["set-static", "enp0s3", "192.168.1.50/24", "192.168.1.1", "1.1.1.1,8.8.8.8"], config)
    text = config.read_text()
    assert "[interface enp0s3]" in text
    assert "mode = static" in text
    assert "static_ip = 192.168.1.50/24" in text
    assert "gateway = 192.168.1.1" in text
    assert "dns = 1.1.1.1,8.8.8.8" in text


def test_connect_and_disconnect_wifi(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text("[interface enp0s3]\nmode = dhcp\n")
    run(["connect", "TestNet", "secret123"], config)
    text = config.read_text()
    assert "[wifi]" in text
    assert "interface = wlan0" in text
    assert "ssid = TestNet" in text
    assert "psk = secret123" in text
    assert "[interface enp0s3]" in text

    run(["disconnect"], config)
    text = config.read_text()
    assert "[wifi]" not in text
    assert "ssid = TestNet" not in text
    assert "[interface enp0s3]" in text


def test_status_reports_configuration(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text(
        "[interface enp0s3]\n"
        "mode = static\n"
        "static_ip = 10.0.0.2/24\n"
        "[wifi]\n"
        "interface = wlan0\n"
        "ssid = TestNet\n"
        "psk = secret123\n"
    )
    result = run(["status"], config)
    assert "interface enp0s3" in result.stdout
    assert "TestNet" in result.stdout


def _make_link(netdir: Path, name: str, kind: int, wireless: bool = False) -> None:
    link = netdir / name
    link.mkdir()
    (link / "type").write_text(f"{kind}\n")
    if wireless:
        (link / "wireless").mkdir()


def test_wired_interfaces_skips_pseudo_links(tmp_path: Path) -> None:
    # /sys/class/net lists kernel pseudo interfaces (sit0, ip6tnl0, dummy0) that
    # have no carrier to lease from. Handing sit0 to dhcpcd produced
    # "sit0: unsupported interface type" and delayed the lease on eth0, which is
    # how a fresh boot ended up without an address.
    netdir = tmp_path / "net"
    netdir.mkdir()
    _make_link(netdir, "lo", 772)
    _make_link(netdir, "eth0", 1)
    _make_link(netdir, "sit0", 776)
    _make_link(netdir, "dummy0", 1)
    _make_link(netdir, "ip6tnl0", 769)
    _make_link(netdir, "wlan0", 1, wireless=True)

    env = os.environ.copy()
    env["GRINTION_SYSFS_NET"] = str(netdir)
    result = subprocess.run(
        ["sh", "-c", '. "$1"; network_wired_interfaces', "sh", str(LIB)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert sorted(result.stdout.split()) == ["dummy0", "eth0"]


def test_network_service_uses_the_filtered_scan() -> None:
    script = (REPO_ROOT / "etc" / "sv" / "network" / "run").read_text()
    assert "network_wired_interfaces" in script
    assert "/sys/class/net/*" not in script


def test_timesync_waits_for_resolvable_peers_and_logs_off_console() -> None:
    # Starting ntpd before DHCP completed made busybox print "bad address" for
    # every pool.ntp.org peer directly on tty1, then exit into a fast restart
    # loop. The service must wait for DNS, log to a file and back off.
    script = (REPO_ROOT / "etc" / "sv" / "timesync" / "run").read_text()
    assert "exec >>/var/log/timesync.log 2>&1" in script
    assert "getent hosts" in script
    assert "peers_resolve" in script
    assert "retrying in 60 seconds" in script
    assert "exec /usr/bin/busybox ntpd -n -N" not in script


def test_dry_run_does_not_modify(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    original = "[interface enp0s3]\nmode = dhcp\n"
    config.write_text(original)
    result = subprocess.run(
        [str(CLI), "--config", str(config), "--no-apply", "--dry-run",
         "set-static", "enp0s3", "10.0.0.2/24"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GRINTION_NETWORK_LIB": str(LIB)},
    )
    assert result.returncode == 0
    assert "would configure" in result.stdout
    assert config.read_text() == original
