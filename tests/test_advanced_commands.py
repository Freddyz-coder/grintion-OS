from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "bin"

NEW_TOOLS = [
    "grintion-disk",
    "grintion-mount",
    "grintion-swap",
    "grintion-space",
    "grintion-service",
    "grintion-timer",
    "grintion-dns",
    "grintion-netdiag",
    "grintion-firewall",
    "grintion-ssh",
    "grintion-cert",
    "grintion-logs",
    "grintion-load",
    "grintion-bench",
    "grintion-modules",
    "grintion-time",
]


def env_for(**extra: object) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GRINTION_")}
    env.update({key: str(value) for key, value in extra.items()})
    return env


def run_tool(tool: str, *args: str, env: dict[str, str] | None = None,
             timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(BIN / tool), *args],
        capture_output=True,
        text=True,
        env=env or env_for(),
        timeout=timeout,
        check=False,
    )


def json_out(result: subprocess.CompletedProcess) -> dict:
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


@pytest.mark.parametrize("tool", NEW_TOOLS)
def test_new_tools_are_executable_and_document_themselves(tool: str) -> None:
    path = BIN / tool
    assert path.is_file(), tool
    assert os.access(path, os.X_OK), tool
    result = run_tool(tool, "--help")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_disk_inventory_fstab_and_usage(tmp_path: Path) -> None:
    listing = json_out(run_tool("grintion-disk", "list", "--json"))
    assert listing["schema"] == 1
    assert isinstance(listing["devices"], list)

    mountpoint = tmp_path / "data"
    mountpoint.mkdir()
    good = tmp_path / "fstab.good"
    good.write_text(
        "# test fstab\n"
        "/dev/null\t/data\text4\tdefaults\t0\t2\n", encoding="utf-8"
    )
    result = run_tool("grintion-disk", "fstab", "--path", str(good), "--json")
    data = json_out(result)
    assert data["problems"] == []
    assert data["entries"] == 1

    bad = tmp_path / "fstab.bad"
    bad.write_text("/dev/null /data ext4\n", encoding="utf-8")
    result = run_tool("grintion-disk", "fstab", "--path", str(bad), "--json")
    assert result.returncode == 1
    problems = json.loads(result.stdout)["problems"]
    assert any("6 fields" in item["problem"] for item in problems)

    usage = json_out(run_tool("grintion-disk", "usage", "--json"))
    assert usage["schema"] == 1
    assert usage["filesystems"]

    trim = json_out(run_tool("grintion-disk", "trim", "--dry-run", "--json"))
    assert trim["schema"] == 1


def test_mount_add_remove_roundtrip(tmp_path: Path) -> None:
    env = env_for(GRINTION_ROOT=tmp_path, GRINTION_FSTAB=tmp_path / "etc/fstab")
    result = run_tool("grintion-mount", "add", "10.0.0.1:/export", "/mnt/export",
                      "--fstype", "nfs", "--no-mount", "--json", env=env)
    payload = json_out(result)
    assert payload["mounted"] is False
    fstab = (tmp_path / "etc/fstab").read_text(encoding="utf-8")
    assert "/mnt/export" in fstab and "nfs" in fstab

    result = run_tool("grintion-mount", "remove", "/mnt/export", "--json", env=env)
    assert json_out(result)["removed"] == 1
    assert "/mnt/export" not in (tmp_path / "etc/fstab").read_text(encoding="utf-8")

    refusal = run_tool("grintion-mount", "remove", "/", env=env)
    assert refusal.returncode != 0
    assert "refusing" in refusal.stderr

    mounts = json_out(run_tool("grintion-mount", "list", "--json"))
    assert mounts["mounts"]


def test_swap_status_and_dry_runs(tmp_path: Path) -> None:
    status = json_out(run_tool("grintion-swap", "status", "--json"))
    assert status["schema"] == 1
    assert isinstance(status["swaps"], list)
    assert isinstance(status["swappiness"], int)

    planned = json_out(run_tool(
        "grintion-swap", "add-file", str(tmp_path / "swapfile"),
        "--size", "64", "--dry-run", "--json",
    ))
    assert planned["dry_run"] is True

    missing = run_tool("grintion-swap", "remove", "/dev/does-not-exist", "--json")
    assert missing.returncode == 1

    current = json_out(run_tool("grintion-swap", "swappiness", "--json"))
    assert 0 <= current["swappiness"] <= 200
    planned = json_out(run_tool("grintion-swap", "swappiness", "10", "--dry-run",
                                "--json", env=env_for(GRINTION_ROOT=tmp_path)))
    assert planned["swappiness"] == 10


def test_space_scan_reports_largest_directory(tmp_path: Path) -> None:
    (tmp_path / "small").mkdir()
    (tmp_path / "small" / "a.bin").write_bytes(b"a" * 1024)
    (tmp_path / "large").mkdir()
    (tmp_path / "large" / "b.bin").write_bytes(b"b" * (2 * 1024 * 1024))
    result = run_tool("grintion-space", str(tmp_path), "--apparent-size",
                      "--depth", "1", "--json")
    data = json_out(result)
    assert data["total_bytes"] >= 2 * 1024 * 1024
    assert data["files"] == 2
    assert data["entries"][0]["path"].endswith("large")
    assert data["largest_files"][0]["path"].endswith("b.bin")

    inodes = json_out(run_tool("grintion-space", str(tmp_path), "--apparent-size",
                                "--inodes", "--json"))
    assert inodes["files"] == 2


def test_service_enable_list_and_logs(tmp_path: Path) -> None:
    service = tmp_path / "etc/sv/demo"
    service.mkdir(parents=True)
    (service / "run").write_text("#!/bin/sh\nexec sleep 100\n", encoding="utf-8")
    os.chmod(service / "run", 0o755)
    env = env_for(GRINTION_ROOT=tmp_path)

    listing = json_out(run_tool("grintion-service", "list", "--json", env=env))
    demo = next(item for item in listing["services"] if item["name"] == "demo")
    assert demo["enabled"] is False

    enabled = json_out(run_tool("grintion-service", "enable", "demo", "--json", env=env))
    assert enabled["enabled"] is True
    assert (tmp_path / "var/service/demo").is_symlink()

    status = json_out(run_tool("grintion-service", "status", "demo", "--json", env=env))
    assert status["service"]["enabled"] is True

    (tmp_path / "var/log").mkdir(parents=True)
    (tmp_path / "var/log/demo.log").write_text("first\nsecond\n", encoding="utf-8")
    logs = json_out(run_tool("grintion-service", "logs", "demo", "--json", env=env))
    assert logs["lines"][-1] == "second"

    script = json_out(run_tool("grintion-service", "cat", "demo", "--json", env=env))
    assert "sleep 100" in script["content"]

    disabled = json_out(run_tool("grintion-service", "disable", "demo", "--json", env=env))
    assert disabled["enabled"] is False
    assert not (tmp_path / "var/service/demo").exists()


def test_timer_validation_add_run_and_remove(tmp_path: Path) -> None:
    weekday = run_tool("grintion-timer", "validate", "cron 0 3 * * mon-fri", "--json")
    assert len(json_out(weekday)["next_runs"]) == 3
    assert run_tool("grintion-timer", "validate", "monthly 31 04:00").returncode == 0
    assert run_tool("grintion-timer", "validate", "not a schedule").returncode == 1

    env = env_for(GRINTION_ROOT=tmp_path)
    added = json_out(run_tool(
        "grintion-timer", "add", "backup", "--schedule", "daily 03:30",
        "--command", "/bin/true", "--json", env=env,
    ))
    assert added["enabled"] is True
    timer_file = tmp_path / "etc/grintion/timers.d/backup.timer"
    assert timer_file.is_file()
    run_script = tmp_path / "etc/sv/grintion-timer-backup/run"
    assert "daemon backup" in run_script.read_text(encoding="utf-8")

    listing = json_out(run_tool("grintion-timer", "list", "--json", env=env))
    assert listing["timers"][0]["name"] == "backup"

    ran = json_out(run_tool("grintion-timer", "run-now", "backup", "--json", env=env))
    assert ran["exit"] == 0
    state = json.loads((tmp_path / "var/lib/grintion/timers/backup.json").read_text())
    assert state["runs"] == 1 and state["last_status"] == "ok"

    removed = json_out(run_tool("grintion-timer", "remove", "backup", "--json", env=env))
    assert removed["removed"] == "backup"
    assert not timer_file.exists()


def test_logs_errors_search_and_rotation(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text(
        "started cleanly\nconnection refused by peer\nERROR: disk full\n",
        encoding="utf-8",
    )
    (log_dir / "kernel").write_text("panic: something bad\n", encoding="utf-8")
    env = env_for(GRINTION_LOG_DIR=log_dir)

    listing = json_out(run_tool("grintion-logs", "list", "--json", env=env))
    assert listing["count"] == 2

    errors = run_tool("grintion-logs", "errors", "--json", env=env)
    assert errors.returncode == 0
    report = json.loads(errors.stdout)
    assert report["total"] == 3
    assert report["files"][0]["count"] >= 1

    strict = run_tool("grintion-logs", "errors", "--strict", env=env)
    assert strict.returncode == 1

    matches = json_out(run_tool("grintion-logs", "grep", "refused", "--json", env=env))
    assert matches["matches"][0]["text"].startswith("connection refused")

    tail = json_out(run_tool("grintion-logs", "tail", "app", "-n", "2", "--json", env=env))
    assert tail["lines"][-1].startswith("ERROR")

    rotate = json_out(run_tool("grintion-logs", "rotate", "--max-size", "1",
                               "--dry-run", "--json", env=env))
    assert len(rotate["rotated"]) == 2

    outside = run_tool("grintion-logs", "clear", "/etc/hostname", env=env)
    assert outside.returncode == 1
    assert "outside" in outside.stderr


def test_firewall_block_dry_run_and_service_wiring(tmp_path: Path) -> None:
    env = env_for(
        GRINTION_FIREWALL_STATE=tmp_path / "state.json",
        GRINTION_FIREWALL_RULES=tmp_path / "rules.nft",
    )
    planned = json_out(run_tool("grintion-firewall", "block", "23/tcp",
                                "--comment", "telnet", "--dry-run", "--json", env=env))
    assert planned["dry_run"] is True
    assert "tcp dport 23 drop" in planned["rules"]
    assert not (tmp_path / "state.json").exists()

    state = {
        "schema": 1,
        "entries": [
            {"id": 1, "kind": "port", "value": "23", "protocol": "tcp",
             "direction": "in", "comment": "telnet", "created": 0},
            {"id": 2, "kind": "address", "value": "10.0.0.0/8",
             "family": "ip", "protocol": "any", "direction": "both",
             "comment": "lab", "created": 0},
        ],
    }
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    listed = json_out(run_tool("grintion-firewall", "list", "--json", env=env))
    assert len(listed["entries"]) == 2

    applied = json_out(run_tool("grintion-firewall", "apply", "--dry-run",
                                "--json", env=env))
    assert applied["applied"] is False

    removed = json_out(run_tool("grintion-firewall", "unblock", "1",
                                "--dry-run", "--json", env=env))
    assert removed["removed"]["id"] == 1

    run_script = (REPO_ROOT / "etc/sv/firewall/run").read_text(encoding="utf-8")
    assert "grintion-firewall apply --quiet" in run_script
    assert "apply_blocklist\n        exec sleep 86400" in run_script
    assert run_script.count("apply_blocklist") == 3  # definition plus two call sites


def test_dns_status_set_add_remove_and_check(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/resolv.conf").write_text(
        "nameserver 1.1.1.1\nsearch lan\noptions edns0\n", encoding="utf-8")
    (tmp_path / "etc/resolv.conf.head").write_text("nameserver 8.8.8.8\n",
                                                   encoding="utf-8")
    (tmp_path / "etc/hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")
    env = env_for(GRINTION_ROOT=tmp_path)

    status = json_out(run_tool("grintion-dns", "status", "--json", env=env))
    assert status["nameservers"] == ["1.1.1.1"]
    assert status["head"] == ["8.8.8.8"]

    configured = json_out(run_tool("grintion-dns", "set", "9.9.9.9",
                                   "--search", "lab", "--json", env=env))
    assert configured["nameservers"] == ["9.9.9.9"]
    head = (tmp_path / "etc/resolv.conf.head").read_text(encoding="utf-8")
    assert "nameserver 9.9.9.9" in head and "search lab" in head
    live = (tmp_path / "etc/resolv.conf").read_text(encoding="utf-8")
    assert "nameserver 9.9.9.9" in live
    assert "options edns0" in live  # non-resolver directives are preserved

    checked = json_out(run_tool("grintion-dns", "check", "--json", env=env))
    assert checked["problems"] == []

    added = json_out(run_tool("grintion-dns", "add", "149.112.112.112", "--json", env=env))
    assert "149.112.112.112" in added["nameservers"]
    removed = json_out(run_tool("grintion-dns", "remove", "149.112.112.112",
                                "--json", env=env))
    assert removed["nameservers"] == ["9.9.9.9"]

    assert run_tool("grintion-dns", "set", "not-an-ip", env=env).returncode == 2


def test_netdiag_summary_dns_and_tcp(tmp_path: Path) -> None:
    summary = json_out(run_tool("grintion-netdiag", "summary", "--json"))
    assert summary["interfaces"] >= 1
    assert "resolvers" in summary

    interfaces = json_out(run_tool("grintion-netdiag", "interfaces", "--json"))
    assert interfaces["interfaces"]
    assert all(entry["mac"] in ("", "<redacted>") for entry in interfaces["interfaces"])

    resolved = json_out(run_tool("grintion-netdiag", "dns", "localhost", "--json"))
    assert resolved["results"][0]["ok"] is True

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        open_result = run_tool("grintion-netdiag", "tcp", "127.0.0.1", str(port),
                               "--timeout", "2", "--json")
        assert open_result.returncode == 0, open_result.stderr
        assert json.loads(open_result.stdout)["results"][0]["ok"] is True
    finally:
        server.close()

    closed = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    closed.bind(("127.0.0.1", 0))
    closed_port = closed.getsockname()[1]
    closed.close()
    refused = run_tool("grintion-netdiag", "tcp", "127.0.0.1", str(closed_port),
                       "--timeout", "1")
    assert refused.returncode == 1


def test_ssh_keygen_keys_and_audit(tmp_path: Path) -> None:
    env = env_for(GRINTION_USER_HOME=tmp_path,
                  GRINTION_SSHD_CONFIG=tmp_path / "no-sshd-config")
    created = json_out(run_tool("grintion-ssh", "keygen", "id_test",
                                "--type", "ed25519", "--no-passphrase",
                                "--json", env=env))
    assert created["type"] == "ed25519"
    key = tmp_path / ".ssh/id_test"
    assert key.is_file()
    assert stat.S_IMODE(key.stat().st_mode) == 0o600

    keys = json_out(run_tool("grintion-ssh", "keys", "--json", env=env))
    assert keys["keys"][0]["bits"] == 256
    assert keys["keys"][0]["mode_ok"] is True

    assert run_tool("grintion-ssh", "audit", env=env).returncode == 0

    config = tmp_path / ".ssh/config"
    config.write_text(
        "Host *\n"
        "  StrictHostKeyChecking no\n"
        "  ForwardAgent yes\n"
        "  Ciphers 3des-cbc\n", encoding="utf-8")
    audit = run_tool("grintion-ssh", "audit", "--json", env=env)
    assert audit.returncode == 1
    findings = json.loads(audit.stdout)["findings"]
    assert len(findings) >= 3

    known = json_out(run_tool("grintion-ssh", "known-hosts", "--json", env=env))
    assert known["count"] == 0


def test_cert_generate_info_verify_and_expiry(tmp_path: Path) -> None:
    env = env_for(GRINTION_TLS_DIR=tmp_path / "tls")
    generated = json_out(run_tool(
        "grintion-cert", "generate", "site", "--cn", "example.test",
        "--days", "10", "--san", "example.test,127.0.0.1", "--json", env=env,
    ))
    certificate = Path(generated["certificate"])
    key = Path(generated["key"])
    assert certificate.is_file() and key.is_file()
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert len(generated["sans"]) == 2  # no duplicate DNS entry

    info = json_out(run_tool("grintion-cert", "info", str(certificate), "--json"))
    assert "example.test" in info["subject"]
    assert "IP Address:127.0.0.1" in info["sans"]

    verified = run_tool("grintion-cert", "verify", str(certificate),
                        "--ca", str(certificate), "--hostname", "example.test",
                        "--json")
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["ok"] is True

    expiry = json_out(run_tool("grintion-cert", "expiry", "--days", "30", "--json", env=env))
    assert expiry["expired"] == 0
    assert len(expiry["candidates"]) == 1

    fingerprint = json_out(run_tool("grintion-cert", "fingerprint",
                                    str(certificate), "--json"))
    assert fingerprint["sha256"].count(":") == 31

    listing = json_out(run_tool("grintion-cert", "list", "--json", env=env))
    assert len(listing["managed"]) == 1

    escape = run_tool("grintion-cert", "generate", "../escape", "--json", env=env)
    assert escape.returncode == 2
    assert not (tmp_path / "escape").exists()


def test_bench_quick_runs_and_compare(tmp_path: Path) -> None:
    cpu = json_out(run_tool("grintion-bench", "cpu", "--quick", "--duration", "0.05",
                            "--json"))
    assert cpu["cpu"]["mb_per_second"] > 0

    memory = json_out(run_tool("grintion-bench", "memory", "--quick", "--memory", "2",
                               "--json"))
    assert memory["memory"]["read_mb_per_second"] > 0

    disk = json_out(run_tool("grintion-bench", "disk", "--quick", "--size", "1",
                             "--random-reads", "10", "--path", str(tmp_path), "--json"))
    assert disk["disk"]["random_4k_iops"] > 0
    assert not list(tmp_path.glob("grintion-bench-*"))

    baseline = tmp_path / "baseline.json"
    saved = json_out(run_tool("grintion-bench", "all", "--quick", "--out",
                              str(baseline), "--json"))
    assert saved["schema"] == 1
    comparison = json_out(run_tool("grintion-bench", "compare", str(baseline),
                                   "--json"))
    assert comparison["comparison"]
    assert {row["verdict"] for row in comparison["comparison"]} <= {
        "faster", "slower", "same"}


def test_load_snapshot_top_and_threshold() -> None:
    show = json_out(run_tool("grintion-load", "show", "--interval", "0.05", "--json"))
    assert show["schema"] == 1
    assert "load1" in show["load"]
    assert show["memory"]["total_bytes"] > 0

    top = json_out(run_tool("grintion-load", "top", "--interval", "0.05",
                            "-n", "3", "--json"))
    assert len(top["processes"]) <= 3
    assert all("cpu_percent" in entry for entry in top["processes"])

    psi = run_tool("grintion-load", "psi", "--json")
    assert psi.returncode == 0, psi.stderr
    assert json.loads(psi.stdout)["schema"] == 1

    ok = run_tool("grintion-load", "threshold", "--interval", "0.05",
                  "--load", "1000", "--cpu", "100", "--mem", "100")
    assert ok.returncode == 0
    exceeded = run_tool("grintion-load", "threshold", "--interval", "0.05",
                        "--load", "-1", "--exit-code")
    assert exceeded.returncode == 1


def test_modules_inventory_blacklist_and_taint(tmp_path: Path) -> None:
    listing = json_out(run_tool("grintion-modules", "list", "--json"))
    assert listing["count"] >= 0
    assert all("name" in module for module in listing["modules"])

    taint = json_out(run_tool("grintion-modules", "taint", "--json"))
    assert isinstance(taint["tainted"], int)
    assert taint["clean"] == (taint["tainted"] == 0)

    builtin = json_out(run_tool("grintion-modules", "builtin", "--json"))
    assert isinstance(builtin["modules"], list)

    env = env_for(GRINTION_ROOT=tmp_path)
    added = json_out(run_tool("grintion-modules", "blacklist", "zram",
                              "--json", env=env))
    assert added["action"] == "added"
    blacklist = tmp_path / "etc/modprobe.d/grintion-blacklist.conf"
    assert "blacklist zram" in blacklist.read_text(encoding="utf-8")

    removed = json_out(run_tool("grintion-modules", "blacklist", "zram",
                                "--remove", "--json", env=env))
    assert removed["action"] == "removed"
    assert "blacklist zram" not in blacklist.read_text(encoding="utf-8")


def test_time_status_ntp_peers_and_timezone(tmp_path: Path) -> None:
    status = json_out(run_tool("grintion-time", "status", "--json"))
    assert status["schema"] == 1
    assert status["epoch"] > 0

    ntp = tmp_path / "etc/ntp.conf"
    ntp.parent.mkdir(parents=True)
    ntp.write_text("# peers\nserver pool.ntp.org\n", encoding="utf-8")
    env = env_for(GRINTION_ROOT=tmp_path, GRINTION_NTP_CONF=ntp)

    servers = json_out(run_tool("grintion-time", "servers", "--json", env=env))
    assert servers["servers"] == ["pool.ntp.org"]

    json_out(run_tool("grintion-time", "add-server", "time.example.net",
                      "--json", env=env))
    servers = json_out(run_tool("grintion-time", "servers", "--json", env=env))
    assert "time.example.net" in servers["servers"]

    json_out(run_tool("grintion-time", "remove-server", "time.example.net",
                      "--json", env=env))
    assert "time.example.net" not in ntp.read_text(encoding="utf-8")

    zone = tmp_path / "usr/share/zoneinfo/Test/Zone"
    zone.parent.mkdir(parents=True)
    zone.write_bytes(b"TZif")
    result = run_tool("grintion-time", "tz", "Test/Zone", "--json", env=env)
    assert json_out(result)["timezone"] == "Test/Zone"
    assert (tmp_path / "etc/localtime").is_symlink()
    assert (tmp_path / "etc/timezone").read_text(encoding="utf-8").strip() == "Test/Zone"

    planned = run_tool("grintion-time", "set", "2026-11-14T12:00:00",
                       "--dry-run", "--json", env=env)
    payload = json_out(planned)
    assert payload["dry_run"] is True
    assert payload["time"] == "2026-11-14 12:00:00"

    traversal = run_tool("grintion-time", "tz", "/etc/passwd", env=env)
    assert traversal.returncode == 2


def test_help_and_welcome_advertise_the_new_tools() -> None:
    storage = run_tool("grintion-help", "storage")
    assert storage.returncode == 0
    assert "grintion-disk" in storage.stdout

    welcome = json_out(run_tool("grintion-welcome", "--json"))
    names = {tool["name"] for tool in welcome["tools"]}
    assert {"grintion-service", "grintion-timer", "grintion-disk",
            "grintion-logs", "grintion-netdiag", "grintion-firewall",
            "grintion-bench", "grintion-ssh", "grintion-cert"} <= names
