from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
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


def _fake_pacman(
    path: Path,
    *,
    stall: bool = False,
    size: int = 1048576,
    download_seconds: float = 0.2,
) -> None:
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'case " $* " in\n'
        f'  *" -Sp "*) printf "core\\tfirefox\\t160.0-1\\t{size}\\tfirefox-160.0-1-x86_64.pkg.tar.zst\\n"; exit 0 ;;\n'
        "esac\n"
        'echo ":: Retrieving packages..."\n'
        'echo " firefox-160.0-1-x86_64 downloading..."\n'
        + (
            "sleep 30\n"
            if stall
            else 'dd if=/dev/zero of="$FAKE_CACHE/firefox-160.0-1-x86_64.pkg.tar.zst" '
            "bs=1024 count=512 status=none\n"
            f"sleep {download_seconds}\n"
            'echo ":: Processing package changes..."\n'
            'echo "(1/1) installing firefox"\n'
            'echo ":: Running post-transaction hooks..."\n'
            'echo "(1/1) Updating icon caches..."\n'
        )
        + "exit 0\n"
    )
    path.chmod(0o755)


def _run_cli(
    tmp_path: Path,
    *args: str,
    stall: bool = False,
    size: int = 1048576,
    download_seconds: float = 0.2,
) -> subprocess.CompletedProcess:
    cache = tmp_path / "cache"
    cache.mkdir()
    fake = tmp_path / "pacman"
    _fake_pacman(
        fake, stall=stall, size=size, download_seconds=download_seconds
    )
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


def _write_sync_db(root: Path, filename: str, csize: int) -> None:
    sync = root / "var/lib/pacman/sync"
    sync.mkdir(parents=True)
    desc = (
        b"%NAME%\nfirefox\n\n%FILENAME%\n"
        + filename.encode()
        + b"\n\n%CSIZE%\n"
        + str(csize).encode()
        + b"\n\n"
    )
    with tarfile.open(sync / "core.db", "w:gz") as archive:
        info = tarfile.TarInfo("firefox-160.0-1/desc")
        info.size = len(desc)
        archive.addfile(info, io.BytesIO(desc))


# pacman 7 prints %s as 0 for packages that come from a sync database. The
# plan must recover the real size from the database instead of showing
# "0 B / total" for a transaction that is downloading gigabytes.
def test_progress_plan_fills_zero_sizes_from_sync_database(tmp_path: Path) -> None:
    _write_sync_db(tmp_path, "firefox-160.0-1-x86_64.pkg.tar.zst", 2 * 1024 * 1024)
    fake = tmp_path / "pacman"
    _fake_pacman(fake, size=0)
    plan = progress.build_plan([str(fake), "-S", "--noconfirm", "firefox"], tmp_path)
    assert plan is not None
    assert plan.total_download == 2 * 1024 * 1024
    assert plan.unknown_size_count == 0


def test_progress_counts_partial_downloads_for_unknown_sizes(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    plan = progress.PacmanPlan(
        packages=[
            progress.PlannedPackage(
                repo="core",
                name="firefox",
                version="160.0-1",
                size=0,
                filename="firefox-160.0-1-x86_64.pkg.tar.zst",
            )
        ],
        total_download=0,
    )
    (cache / "firefox-160.0-1-x86_64.pkg.tar.zst.part").write_bytes(b"x" * 4096)
    assert progress.measured_download(plan, cache) == 4096


# A plan without usable sizes must still show the bytes that arrive, and the
# watchdog must see them as activity, instead of a frozen "0 B / <total>".
def test_progress_shows_received_bytes_when_size_is_unknown(tmp_path: Path) -> None:
    result = _run_cli(
        tmp_path, "--stall-seconds", "10", size=0, download_seconds=0.6
    )
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "0 B / " not in combined
    assert "received" in combined
    assert "512 KiB received" in combined


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


def test_progress_counts_pacman7_download_subdirs(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    dl_dir = cache / "download-abc123"
    dl_dir.mkdir(parents=True)
    plan = progress.PacmanPlan(
        packages=[
            progress.PlannedPackage(
                repo="extra",
                name="plasma-meta",
                version="6.8-1",
                size=16384,
                filename="plasma-meta-6.8-1-any.pkg.tar.zst",
            )
        ],
        total_download=16384,
    )
    (dl_dir / "plasma-meta-6.8-1-any.pkg.tar.zst.part").write_bytes(b"x" * 8192)
    assert progress.measured_download(plan, cache) == 8192
    assert progress.directory_size(cache) == 8192


def test_progress_clears_stale_pacman_lock_on_stall(tmp_path: Path) -> None:
    (tmp_path / "var/lib/pacman").mkdir(parents=True)
    lock_file = tmp_path / "var/lib/pacman/db.lck"
    lock_file.write_text("")
    result = _run_cli(
        tmp_path,
        "--stall-seconds",
        "0.5",
        stall=True,
    )
    assert result.returncode == 124
    assert not lock_file.exists()
