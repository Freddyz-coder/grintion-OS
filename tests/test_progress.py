from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "bin" / "pkg-progress"

sys.path.insert(0, str(REPO_ROOT / "bin"))
from garblib import progress  # noqa: E402


def test_progress_formatting_helpers() -> None:
    assert progress.format_bytes(0) == "0 B"
    assert progress.format_bytes(1024) == "1.00 KiB"
    assert progress.format_bytes(1024 * 1024) == "1.00 MiB"
    assert progress.format_duration(0) == "00:00"
    assert progress.format_duration(65) == "01:05"
    assert progress.format_duration(3665) == "1:01:05"
    assert progress.render_bar(0.0, width=4) == "[----]"
    assert progress.render_bar(0.5, width=4) == "[##--]"
    assert progress.render_bar(1.0, width=4) == "[####]"


def test_progress_plan_is_built_without_downloading() -> None:
    assert progress.operation_of(["pacman", "-S", "--needed", "firefox"]) == "install"
    assert progress.operation_of(["pacman", "-Syu"]) == "upgrade"
    assert progress.operation_of(["pacman", "-Sy"]) == "update"
    assert progress.operation_of(["pacman", "-Rns", "firefox"]) == "remove"


def _fake_pacman(path: Path, *, stall: bool = False) -> None:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'case " $* " in\n'
        '  *" -Sp "*) printf "core\\tfirefox\\t160.0-1\\t1048576\\tfirefox-160.0-1-x86_64.pkg.tar.zst\\n"; exit 0 ;;\n'
        "esac\n"
        'echo ":: Retrieving packages..."\n'
        'echo " firefox-160.0-1-x86_64 downloading..."\n'
        + (
            "sleep 30\n"
            if stall
            else 'dd if=/dev/zero of="$FAKE_CACHE/firefox-160.0-1-x86_64.pkg.tar.zst" '
            "bs=1024 count=512 status=none\n"
            "sleep 0.2\n"
            'echo ":: Processing package changes..."\n'
            'echo "(1/1) installing firefox"\n'
            'echo ":: Running post-transaction hooks..."\n'
            'echo "(1/1) Updating icon caches..."\n'
        )
        + "exit 0\n"
    )
    path.chmod(0o755)


def _run_cli(tmp_path: Path, *args: str, stall: bool = False) -> subprocess.CompletedProcess:
    cache = tmp_path / "cache"
    cache.mkdir()
    fake = tmp_path / "pacman"
    _fake_pacman(fake, stall=stall)
    env = os.environ.copy()
    env["FAKE_CACHE"] = str(cache)
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(tmp_path),
            "--cache-dir",
            str(cache),
            "--log",
            str(tmp_path / "transaction.log"),
            "--interval",
            "0.2",
            *args,
            "--",
            str(fake),
            "-S",
            "--noconfirm",
            "firefox",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_progress_cli_hides_raw_output_and_shows_phases(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, "--stall-seconds", "10")
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "Resolving package transaction..." in combined
    assert "package(s) queued" in combined
    assert "Downloading" in combined
    assert "Installing" in combined
    assert "package(s), 1.00 MiB download" in combined
    # The raw pacman transcript belongs in the log, not on the console.
    assert ":: Retrieving packages..." not in combined
    assert ":: Processing package changes..." not in combined
    log = (tmp_path / "transaction.log").read_text()
    assert ":: Retrieving packages..." in log
    assert "(1/1) installing firefox" in log


def test_progress_cli_stops_a_stalled_transaction(tmp_path: Path) -> None:
    result = _run_cli(
        tmp_path,
        "--stall-seconds",
        "0.5",
        stall=True,
    )
    assert result.returncode == 124
    combined = result.stdout + result.stderr
    assert "no download or installation progress" in combined
    assert "full package manager log:" in combined


def test_garb_uses_progress_ui_when_forced(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "var/lib/pacman/sync").mkdir(parents=True)
    (root / "var/lib/pacman/sync/core.db").write_text("")
    (root / "var/cache/pacman/pkg").mkdir(parents=True)
    (root / "etc").mkdir()
    fake = tmp_path / "pacman"
    _fake_pacman(fake)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["FAKE_CACHE"] = str(root / "var/cache/pacman/pkg")
    env["GRINTION_PROGRESS"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "bin" / "garb"),
            "--backend",
            "pacman",
            "--root",
            str(root),
            "install",
            "firefox",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "Resolving package transaction..." in combined
    assert "Downloading" in combined
    assert "package(s), 1.00 MiB download" in combined
