from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECURITY = REPO_ROOT / "bin" / "security"
NETWORK = REPO_ROOT / "bin" / "network"
LIB = REPO_ROOT / "etc/grintion/network.lib.sh"
PRIVACY_LIB = REPO_ROOT / "etc/grintion/privacy.lib.sh"


def run(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = os.environ.copy()
    environ.pop("GRINTION_ROOT", None)
    if env:
        environ.update(env)
    return subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def run_shell(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        ["sh", "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def run_bash(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environ = os.environ.copy()
    if env:
        environ.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=environ,
        check=False,
    )


def test_shell_history_is_ram_backed_with_disk_fallback() -> None:
    for relative in ("etc/profile.d/90-grintion-privacy.sh", "etc/bash.bashrc"):
        text = (REPO_ROOT / relative).read_text()
        assert "privacy.lib.sh" in text, relative
        assert "grintion_private_history" in text, relative
        assert "~/.bashrc" in text, relative

    lib = PRIVACY_LIB.read_text()
    assert "stat -f -c %T" in lib and "= tmpfs" in lib
    assert "HISTFILE=/dev/null" in lib
    assert "chmod 600" in lib
    assert "histappend" in lib


def test_history_is_shared_between_terminals_but_not_written_to_disk(tmp_path: Path) -> None:
    shm_root = Path("/dev/shm") / f"grintion-test-{os.getpid()}"
    shm_root.mkdir(mode=0o700)
    try:
        rc = tmp_path / "rc"
        rc.write_text(
            f". {PRIVACY_LIB}\n"
            f"GRINTION_HISTORY_DIR={shm_root}\n"
            "grintion_private_history\n"
        )
        home = tmp_path / "home"
        home.mkdir()
        env = {"HOME": str(home)}

        first = subprocess.run(
            ["bash", "--rcfile", str(rc), "-i"],
            input="echo first-cmd\nexit\n",
            capture_output=True,
            text=True,
            env={**os.environ, **env},
            check=False,
        )
        assert first.returncode == 0, first.stderr

        histories = list(shm_root.glob(".grintion-history-*/history"))
        assert len(histories) == 1
        assert "first-cmd" in histories[0].read_text()
        assert stat.S_IMODE(histories[0].stat().st_mode) == 0o600
        assert stat.S_IMODE(histories[0].parent.stat().st_mode) == 0o700

        # A second terminal sees the first one's commands, so history remains
        # usable while it is only ever stored in RAM.
        second = subprocess.run(
            ["bash", "--rcfile", str(rc), "-i"],
            input="history | grep first-cmd\nexit\n",
            capture_output=True,
            text=True,
            env={**os.environ, **env},
            check=False,
        )
        assert "first-cmd" in second.stdout
        assert not (home / ".bash_history").exists()
        assert not (home / ".lesshst").exists()
    finally:
        shutil.rmtree(shm_root, ignore_errors=True)


def test_history_disabled_when_backing_directory_is_not_tmpfs() -> None:
    # /tmp is a tmpfs on many hosts, so use a directory on the checkout's
    # filesystem to prove the disk-backed fallback is "no history".
    disk_dir = Path(tempfile.mkdtemp(prefix=".privacy-test-", dir=REPO_ROOT))
    try:
        assert subprocess.run(
            ["stat", "-f", "-c", "%T", str(disk_dir)],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip() != "tmpfs"
        result = run_bash(
            f". {PRIVACY_LIB}\n"
            f"GRINTION_HISTORY_DIR={disk_dir}\n"
            "grintion_private_history\n"
            "echo HISTFILE=$HISTFILE\n"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "HISTFILE=/dev/null"
        assert not list(disk_dir.glob(".grintion-history-*"))
    finally:
        shutil.rmtree(disk_dir, ignore_errors=True)


def test_common_tool_history_is_ram_backed_and_fails_closed(tmp_path: Path) -> None:
    shm_root = Path("/dev/shm") / f"grintion-tools-test-{os.getpid()}"
    shm_root.mkdir(mode=0o700)
    try:
        result = run_bash(
            f". {PRIVACY_LIB}\n"
            f"GRINTION_HISTORY_DIR={shm_root}\n"
            "grintion_private_history\n"
            'printf "%s\\n" "$LESSHISTFILE" "$SQLITE_HISTORY" "$PSQL_HISTORY" '
            '"$MYSQL_HISTFILE" "$REDISCLI_HISTFILE" "$GDBHISTFILE" '
            '"$NODE_REPL_HISTORY" "$PYTHON_HISTORY"\n'
        )
        assert result.returncode == 0, result.stderr
        less, *paths = result.stdout.splitlines()
        assert less == "-"
        assert len(paths) == 7
        for path in paths:
            assert path.startswith(str(shm_root / ".grintion-history-")), path
            assert not path.startswith(str(tmp_path))
    finally:
        shutil.rmtree(shm_root, ignore_errors=True)

    # The same fail-closed rule as shell history: no tmpfs means no file at
    # all, not a fallback to a dotfile in $HOME or the root filesystem.
    disk_dir = Path(tempfile.mkdtemp(prefix=".tool-history-test-", dir=REPO_ROOT))
    try:
        result = run_bash(
            f". {PRIVACY_LIB}\n"
            f"GRINTION_HISTORY_DIR={disk_dir}\n"
            "grintion_private_history\n"
            'printf "%s\\n" "$SQLITE_HISTORY" "$NODE_REPL_HISTORY" "$PYTHON_HISTORY"\n'
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["/dev/null", "/dev/null", "/dev/null"]
        assert not list(disk_dir.glob(".grintion-history-*"))
    finally:
        shutil.rmtree(disk_dir, ignore_errors=True)


def test_vim_state_is_ram_backed_and_fails_closed(tmp_path: Path) -> None:
    vim = shutil.which("vim")
    if vim is None:
        return

    shm_root = Path("/dev/shm") / f"grintion-vim-test-{os.getpid()}"
    shm_root.mkdir(mode=0o700)
    home = tmp_path / "home"
    home.mkdir()
    try:
        option_file = tmp_path / "vim-options"
        result = subprocess.run(
            [vim, "-Nu", str(REPO_ROOT / "etc/vimrc"), "-es",
             "-c", f'call writefile([&viminfo, &directory], "{option_file}")',
             "-c", "qall!"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home), "GRINTION_VIMINFO_DIR": str(shm_root)},
            check=False,
        )
        assert result.returncode == 0, result.stderr
        state = shm_root / "viminfo"
        assert state.is_file()
        assert stat.S_IMODE(state.stat().st_mode) == 0o600
        assert stat.S_IMODE(shm_root.stat().st_mode) == 0o700
        options = option_file.read_text().splitlines()
        assert options[0].endswith(str(shm_root / "viminfo"))
        assert options[1].startswith(str(shm_root))
        assert not (home / ".viminfo").exists()
        assert not list(home.glob("*.swp"))
    finally:
        shutil.rmtree(shm_root, ignore_errors=True)

    # A disk-backed override must not be created or used.
    disk_dir = Path(tempfile.mkdtemp(prefix=".vim-state-test-", dir=REPO_ROOT))
    try:
        state_dir = disk_dir / "state"
        home = disk_dir / "home"
        home.mkdir()
        result = subprocess.run(
            [vim, "-Nu", str(REPO_ROOT / "etc/vimrc"), "-es", "-c", "qall!"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home), "GRINTION_VIMINFO_DIR": str(state_dir)},
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert not state_dir.exists()
        assert not (home / ".viminfo").exists()
    finally:
        shutil.rmtree(disk_dir, ignore_errors=True)


def test_dhcp_does_not_advertise_the_hostname() -> None:
    lines = [
        line.strip()
        for line in (REPO_ROOT / "etc/dhcpcd.conf").read_text().splitlines()
    ]
    assert "hostname" not in lines
    assert "nohook hostname" in lines


def test_ipv6_uses_stable_privacy_identifiers() -> None:
    profile = (REPO_ROOT / "etc/sysctl.d/99-grintion.conf").read_text()
    assert "net.ipv6.conf.all.addr_gen_mode = 3" in profile
    assert "net.ipv6.conf.default.addr_gen_mode = 3" in profile
    assert "net.ipv6.conf.all.use_tempaddr = 2" in profile


def test_mac_policy_defaults_to_stable_with_explicit_opt_outs(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    cases = (
        (None, "stable"),
        ("stable", "stable"),
        ("true", "random"),
        ("random", "random"),
        ("false", "off"),
        ("off", "off"),
    )
    for value, expected in cases:
        body = "[interface eth0]\n"
        if value is not None:
            body += f"mac_randomize = {value}\n"
        config.write_text(body)
        result = run_shell(
            f". {LIB}\nnetwork_mac_randomization_mode eth0\n",
            env={"GRINTION_NETWORK_CONF": str(config)},
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected, value


def test_stable_mac_is_consistent_per_network_and_private(tmp_path: Path) -> None:
    privacy_dir = tmp_path / "privacy"
    env = {"GRINTION_PRIVACY_DIR": str(privacy_dir)}
    result = run_shell(
        f". {LIB}\n"
        "stable_local_mac iface:eth0\n"
        "stable_local_mac iface:eth0\n"
        "stable_local_mac iface:eth1\n"
        "stable_local_mac wifi:Cafe\n",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    eth0, eth0_again, eth1, wifi = result.stdout.splitlines()
    assert eth0 == eth0_again
    assert eth0 != eth1
    assert eth0 != wifi
    for mac in (eth0, eth1, wifi):
        assert re.fullmatch(r"02(:[0-9a-f]{2}){5}", mac), mac
        assert mac.split(":")[0] == "02"  # unicast + locally administered

    seed = privacy_dir / "mac-seed"
    assert seed.is_file()
    assert stat.S_IMODE(seed.stat().st_mode) == 0o600
    assert stat.S_IMODE(privacy_dir.stat().st_mode) == 0o700


def test_wifi_scan_privacy_follows_the_policy(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    env = {
        "GRINTION_NETWORK_CONF": str(config),
        "GRINTION_PRIVACY_DIR": str(tmp_path / "privacy"),
    }

    # Only the global form is accepted by every wpa_supplicant release. The
    # association MAC is set on the interface by the service instead.
    for value in (None, "true", "stable"):
        body = "[wifi]\nssid = Cafe\n"
        if value is not None:
            body += f"mac_randomize = {value}\n"
        config.write_text(body)
        result = run_shell(f". {LIB}\nnetwork_wifi_mac_lines\n", env=env)
        assert result.returncode == 0, result.stderr
        assert result.stdout == "preassoc_mac_addr=1\n", value

    config.write_text("[wifi]\nssid = Cafe\nmac_randomize = false\n")
    off = run_shell(f". {LIB}\nnetwork_wifi_mac_lines\n", env=env)
    assert off.returncode == 0
    assert off.stdout == ""


def test_services_use_the_policy_helpers() -> None:
    network_run = (REPO_ROOT / "etc/sv/network/run").read_text()
    assert "apply_mac_policy" in network_run
    assert "set_stable_mac" in network_run
    assert 'mac_randomize)" = "true"' not in network_run
    wpa_run = (REPO_ROOT / "etc/sv/wpa_supplicant/run").read_text()
    assert "network_wifi_mac_lines" in wpa_run
    assert 'stable_local_mac "wifi:$ssid"' in wpa_run
    assert 'ip link set "$iface" address "$wifi_mac"' in wpa_run
    assert "exec wpa_supplicant -q" in wpa_run
    assert "connecting $iface to $ssid" not in wpa_run


def test_set_mac_randomization_targets_the_section_that_is_read(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text(
        "[wifi]\ninterface = wlan0\nssid = Cafe\npsk = secret\n"
    )
    env = {
        "GRINTION_NETWORK_CONF": str(config),
        "GRINTION_NETWORK_LIB": str(LIB),
        "GRINTION_PRIVACY_DIR": str(tmp_path / "privacy"),
    }

    for state, expected in (
        ("off", "mac_randomize = false"),
        ("stable", "mac_randomize = stable"),
        ("random", "mac_randomize = true"),
    ):
        result = run(NETWORK, "--no-apply", "set-mac-randomization", "wlan0", state, env=env)
        assert result.returncode == 0, result.stderr
        text = config.read_text()
        assert expected in text
        assert "psk = secret" in text
        assert "[interface wlan0]" not in text

    # Backwards-compatible aliases still edit the same key.
    result = run(NETWORK, "--no-apply", "set-mac-randomization", "wlan0", "disable", env=env)
    assert result.returncode == 0, result.stderr
    assert "mac_randomize = false" in config.read_text()


def test_network_toggles_preserve_other_interface_keys(tmp_path: Path) -> None:
    config = tmp_path / "network.conf"
    config.write_text(
        "[interface eth0]\nmode = static\nstatic_ip = 192.0.2.10/24\n# keep\n"
    )
    env = {
        "GRINTION_NETWORK_CONF": str(config),
        "GRINTION_NETWORK_LIB": str(LIB),
        "GRINTION_PRIVACY_DIR": str(tmp_path / "privacy"),
    }
    for command in (
        ("set-mac-randomization", "eth0", "enable"),
        ("set-metered", "eth0", "yes"),
    ):
        result = run(NETWORK, "--no-apply", *command, env=env)
        assert result.returncode == 0, result.stderr

    text = config.read_text()
    assert "mode = static" in text
    assert "static_ip = 192.0.2.10/24" in text
    assert "# keep" in text
    assert "mac_randomize = true" in text
    assert "metered = true" in text


def test_drop_inbound_does_not_answer_icmp_timestamp(tmp_path: Path) -> None:
    conf = tmp_path / "security.conf"
    conf.write_text("PROFILE=workstation\nFIREWALL_POLICY=drop_inbound\n")
    captured = tmp_path / "rules.nft"
    nft = tmp_path / "nft"
    nft.write_text(f"#!/bin/sh\ncat > {captured}\nexit 0\n")
    nft.chmod(0o755)

    result = run(
        SECURITY,
        "apply-firewall",
        env={
            "GRINTION_NFT_BIN": str(nft),
            "GRINTION_SECURITY_CONF": str(conf),
            "GRINTION_FIREWALL_FILE": str(tmp_path / "firewall.nft"),
        },
    )
    assert result.returncode == 0, result.stderr
    rules = captured.read_text()
    assert "ip protocol icmp accept" not in rules
    assert "icmp type echo-request accept" in rules
    assert "icmp type destination-unreachable accept" in rules
    assert "icmp type time-exceeded accept" in rules
    assert "icmp type parameter-problem accept" in rules
