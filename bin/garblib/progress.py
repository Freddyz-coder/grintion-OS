"""Grintion package transaction progress UI.

Pacman's own output is captured rather than shown. The complete transcript is
kept in a log file and the operator sees a small, consistent sequence of
phases with package counts, download size, rate, percentage and ETA. The same
renderer is used by grintion-install, grintion-desktop and the pacman backend
of garb, so package operations look the same everywhere.

The renderer is deliberately dependency-free: it only uses the Python standard
library and never imports the rest of garb. This keeps it usable from the live
image and from a source checkout.
"""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Sequence

DEFAULT_STALL_SECONDS = 300.0
TTY_INTERVAL = 0.5
NON_TTY_INTERVAL = 10.0
BAR_WIDTH = 28
SLOW_RATE_BYTES = 100 * 1024
GREEN = "\033[1;32m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
RESET = "\033[0m"

_SHORT_FLAGS = re.compile(r"^-([A-Za-z]+)$")
_VALUE_OPTIONS = {
    "--root",
    "--dbpath",
    "--cachedir",
    "--config",
    "--arch",
    "--ignore",
    "--ignoregroup",
    "--sysroot",
    "--print-format",
    "--overwrite",
    "--color",
}
_DROP_FLAGS = {
    "--noconfirm",
    "--disable-download-timeout",
    "--noprogressbar",
    "--print",
}
_DROP_VALUE_OPTIONS = {"--print-format", "--overwrite", "--color"}
_PLAN_FORMAT = "%r\t%n\t%v\t%s\t%f"

_SECTION_RE = re.compile(r"^::\s*(.*)$")
_PROGRESS_RE = re.compile(
    r"^\((\d+)/(\d+)\)\s+"
    r"(installing|upgrading|reinstalling|downgrading|removing)\s+(\S+)",
    re.IGNORECASE,
)
_HOOK_RE = re.compile(r"^\((\d+)/(\d+)\)\s+(.+)$")
_ERROR_RE = re.compile(r"^\s*(error|warning):\s*(.*)$", re.IGNORECASE)
_DOWNLOAD_RE = re.compile(r"^\s*(\S+)\s+downloading\.\.\.\s*$")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def color_enabled(stream: IO[str]) -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("GRINTION_NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def format_bytes(value: float) -> str:
    value = max(float(value), 0.0)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    if index == 0:
        return f"{int(value)} B"
    if value >= 100:
        return f"{value:.0f} {units[index]}"
    if value >= 10:
        return f"{value:.1f} {units[index]}"
    return f"{value:.2f} {units[index]}"


def format_rate(value: float) -> str:
    return f"{format_bytes(value)}/s"


def format_duration(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def render_bar(fraction: float, width: int = BAR_WIDTH) -> str:
    fraction = min(max(float(fraction), 0.0), 1.0)
    filled = int(round(fraction * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


@dataclass(frozen=True)
class PlannedPackage:
    repo: str
    name: str
    version: str
    size: int
    filename: str


@dataclass
class PacmanPlan:
    packages: list[PlannedPackage]
    total_download: int

    @property
    def total_packages(self) -> int:
        return len(self.packages)

    @property
    def repositories(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for package in self.packages:
            counts[package.repo] = counts.get(package.repo, 0) + 1
        return counts

    @property
    def unknown_size_count(self) -> int:
        """Packages whose download size could not be determined."""
        return sum(1 for package in self.packages if package.size <= 0)

    @property
    def largest(self) -> list[PlannedPackage]:
        return sorted(self.packages, key=lambda item: item.size, reverse=True)[:3]


def operation_of(argv: Sequence[str]) -> str:
    """Return the transaction family without relying on pacman's output."""
    flags: list[str] = []
    for arg in argv[1:]:
        match = _SHORT_FLAGS.match(arg)
        if match is not None:
            flags.append(match.group(1))
    if any("R" in item for item in flags):
        return "remove"
    if any("U" in item for item in flags):
        return "local"
    if any("S" in item for item in flags):
        if any("u" in item for item in flags):
            return "upgrade"
        if _targets(argv):
            return "install"
        return "update"
    return "other"


def _targets(argv: Sequence[str]) -> list[str]:
    targets: list[str] = []
    skip_next = False
    for arg in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            continue
        if arg in _VALUE_OPTIONS:
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        targets.append(arg)
    return targets


def _plan_argv(argv: Sequence[str], operation: str) -> list[str] | None:
    """Build a --print command from a real transaction argument list."""
    if operation not in ("install", "upgrade"):
        return None
    output = [argv[0]]
    index = 1
    while index < len(argv):
        arg = argv[index]
        short = _SHORT_FLAGS.match(arg)
        if short is not None and "S" in short.group(1):
            index += 1
            continue
        if arg == "--":
            index += 1
            continue
        if arg in _DROP_FLAGS:
            index += 1
            continue
        if arg in _DROP_VALUE_OPTIONS:
            index += 2
            continue
        option = arg.split("=", 1)[0]
        if option in _DROP_FLAGS or option in _DROP_VALUE_OPTIONS:
            index += 1
            continue
        output.append(arg)
        index += 1
    output.extend(
        [
            "-Spu" if operation == "upgrade" else "-Sp",
            "--print-format",
            _PLAN_FORMAT,
        ]
    )
    return output


def _sync_db_sizes(root: Path, wanted: dict[str, set[str]]) -> dict[str, int]:
    """Return %CSIZE% values for package filenames from pacman's sync databases.

    pacman 7 prints `%s` as 0 for packages that come from a sync database, so a
    plan built from `-Sp` reports no download size for almost every package.
    The database still stores the compressed size, and reading it keeps the
    progress bar and the stall watchdog working. A missing or unreadable
    database is never fatal: the transaction can still run without a total.
    """
    sizes: dict[str, int] = {}
    wanted = {repo: names for repo, names in wanted.items() if names}
    remaining = sum(len(names) for names in wanted.values())
    if remaining == 0:
        return sizes
    sync_dir = root / "var/lib/pacman/sync"
    for repo, names in wanted.items():
        try:
            archive = tarfile.open(sync_dir / f"{repo}.db", "r:*")
        except (OSError, tarfile.TarError):
            continue
        with archive:
            try:
                for member in archive:
                    if remaining == 0:
                        break
                    if not member.isfile() or not member.name.endswith("/desc"):
                        continue
                    handle = archive.extractfile(member)
                    if handle is None:
                        continue
                    text = handle.read().decode("utf-8", "replace")
                    filename = ""
                    size = 0
                    lines = text.splitlines()
                    for index, line in enumerate(lines):
                        if line == "%FILENAME%" and index + 1 < len(lines):
                            filename = lines[index + 1].strip()
                        elif line == "%CSIZE%" and index + 1 < len(lines):
                            try:
                                size = max(int(lines[index + 1].strip()), 0)
                            except ValueError:
                                size = 0
                    if filename in names and size > 0:
                        sizes[filename] = size
                        names.discard(filename)
                        remaining -= 1
            except (OSError, tarfile.TarError):
                continue
    return sizes


def build_plan(
    argv: Sequence[str], root: Path, timeout: float = 60.0
) -> PacmanPlan | None:
    """Resolve the transaction list and download sizes before it starts.

    `-Sp` does not install or download anything. A failure here is never fatal:
    some pacman configurations cannot print a plan, and the transaction can
    still run with live phase output.
    """
    print_argv = _plan_argv(argv, operation_of(argv))
    if print_argv is None:
        return None
    try:
        result = subprocess.run(
            print_argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    packages: list[PlannedPackage] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        repo, name, version, size_text, filename = parts[:5]
        try:
            size = max(int(size_text), 0)
        except ValueError:
            size = 0
        if not name or not filename:
            continue
        packages.append(
            PlannedPackage(
                repo=repo,
                name=name,
                version=version,
                size=size,
                filename=filename,
            )
        )
    if not packages:
        return None
    missing: dict[str, set[str]] = {}
    for package in packages:
        if package.size <= 0 and package.filename:
            missing.setdefault(package.repo, set()).add(package.filename)
    if missing:
        sizes = _sync_db_sizes(root, missing)
        if sizes:
            packages = [
                PlannedPackage(
                    repo=package.repo,
                    name=package.name,
                    version=package.version,
                    size=sizes.get(package.filename, package.size),
                    filename=package.filename,
                )
                for package in packages
            ]
    return PacmanPlan(packages=packages, total_download=sum(item.size for item in packages))


def cache_directory(argv: Sequence[str], root: Path) -> Path:
    for index, arg in enumerate(argv):
        if arg == "--cachedir" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if arg.startswith("--cachedir="):
            return Path(arg.split("=", 1)[1])
    return root / "var/cache/pacman/pkg"


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _download_subdirs(cache_dir: Path) -> list[Path]:
    subdirs: list[Path] = []
    try:
        with os.scandir(cache_dir) as entries:
            for entry in entries:
                if entry.name.startswith("download-") and entry.is_dir(follow_symlinks=False):
                    subdirs.append(Path(entry.path))
    except OSError:
        pass
    return subdirs


def measured_download(plan: PacmanPlan | None, cache_dir: Path) -> int:
    """Bytes already on disk for the planned packages.

    A known size only clamps a package that is complete. A plan whose sizes
    could not be resolved must still report the bytes pacman actually wrote,
    otherwise the progress line stays at "0 B" while a download is running.
    Pacman 7 downloads partial files inside ``download-*`` subdirectories of
    the cache directory, so check those as well as the cache root.
    """
    if plan is None:
        return 0
    downloaded = 0
    subdirs = _download_subdirs(cache_dir)
    for package in plan.packages:
        complete = _path_size(cache_dir / package.filename)
        partial = _path_size(cache_dir / f"{package.filename}.part")
        for subdir in subdirs:
            partial = max(
                partial,
                _path_size(subdir / package.filename),
                _path_size(subdir / f"{package.filename}.part"),
            )
        actual = max(complete, partial)
        if package.size > 0:
            actual = min(package.size, actual)
        downloaded += actual
    return downloaded


def directory_size(path: Path) -> int:
    total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += directory_size(Path(entry.path))
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _pacman_running() -> bool:
    proc_root = Path("/proc")
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
            if comm == "pacman":
                return True
        except OSError:
            continue
    return False


def clear_stale_pacman_lock(root: str | Path) -> bool:
    """Remove var/lib/pacman/db.lck when no pacman process is running."""
    lock_path = Path(root) / "var/lib/pacman/db.lck"
    if not lock_path.exists():
        return False
    if _pacman_running():
        return False
    try:
        lock_path.unlink()
        return True
    except OSError:
        return False


class _Renderer:
    def __init__(
        self,
        *,
        stream: IO[str],
        quiet: bool,
        verbose: bool,
        colored: bool,
        tty: bool,
        interval: float,
    ) -> None:
        self.stream = stream
        self.quiet = quiet
        self.verbose = verbose
        self.colored = colored
        self.tty = tty
        self.interval = interval
        self.phase = ""
        self.status_active = False
        self.last_status = 0.0
        self.slow_warned = False
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.seen_messages: set[str] = set()

    def _color(self, code: str) -> str:
        return code if self.colored else ""

    def _reset(self) -> str:
        return RESET if self.colored else ""

    def _write(self, text: str, *, newline: bool = True) -> None:
        self.stream.write(text + ("\n" if newline else ""))
        self.stream.flush()

    def finish_status(self) -> None:
        if self.status_active:
            self.stream.write("\n")
            self.stream.flush()
            self.status_active = False

    def header(self, text: str) -> None:
        if self.quiet:
            return
        self.finish_status()
        self._write(f"{self._color(GREEN)}[*]{self._reset()} {text}")

    def success(self, text: str) -> None:
        if self.quiet:
            return
        self.finish_status()
        self._write(f"{self._color(CYAN)}[+]{self._reset()} {text}")

    def warn(self, text: str) -> None:
        self.finish_status()
        self._write(f"{self._color(YELLOW)}[!]{self._reset()} {text}")

    def error(self, text: str) -> None:
        self.finish_status()
        self._write(f"{self._color(RED)}[-]{self._reset()} {text}")

    def raw(self, text: str) -> None:
        if self.verbose:
            self.finish_status()
            self._write(f"    {text}")

    def begin(self, phase: str, text: str) -> None:
        if phase == self.phase:
            return
        self.phase = phase
        self.header(text)

    def status(self, text: str, now: float) -> None:
        if self.quiet:
            return
        if self.tty:
            self.stream.write(f"\r{text}\033[K")
            self.stream.flush()
            self.status_active = True
            return
        if now - self.last_status >= self.interval:
            self.finish_status()
            self._write(text)
            self.last_status = now

    def plan_summary(self, plan: PacmanPlan | None, operation: str) -> None:
        if plan is not None:
            detail = f"{plan.total_packages} package(s) queued"
            if plan.total_download > 0:
                detail += f"; {format_bytes(plan.total_download)} to download"
            unknown = plan.unknown_size_count
            if unknown:
                detail += f" (size unknown for {unknown})"
            self.success(detail)
            repositories = ", ".join(
                f"{name} {count}"
                for name, count in sorted(plan.repositories.items())
                if name
            )
            if repositories:
                self.header(f"Repositories: {repositories}")
            largest = ", ".join(
                f"{item.name} {format_bytes(item.size)}"
                for item in plan.largest
                if item.size > 0
            )
            if largest:
                self.header(f"Largest downloads: {largest}")
            return
        if operation == "remove":
            self.header("Resolving packages to remove...")
        elif operation == "update":
            self.header("Synchronizing package databases...")
        elif operation == "local":
            self.header("Preparing local package transaction...")
        else:
            self.header("Preparing package transaction...")

    def download_status(
        self,
        downloaded: int,
        total: int,
        speed: float,
        elapsed: float,
        current: str,
        unknown_sizes: int = 0,
    ) -> None:
        if total > 0 and unknown_sizes == 0:
            fraction = min(downloaded / total, 1.0)
            text = (
                f"[*] Downloading {render_bar(fraction)} {fraction * 100:3.0f}%  "
                f"{format_bytes(downloaded)} / {format_bytes(total)}"
            )
            if speed > 0:
                eta = (total - downloaded) / speed
                text += f"  {format_rate(speed)}  ETA {format_duration(eta)}"
            else:
                text += "  measuring rate..."
            if current:
                text += f"  {current}"
        elif total > 0:
            # Some package sizes are unknown, so a percentage would be wrong.
            # Show the bytes that are actually arriving instead of a bogus
            # "0 B / total" line that never moves.
            text = (
                f"[*] Downloading packages... {format_bytes(downloaded)} received "
                f"({format_bytes(total)} known)"
            )
            if speed > 0:
                text += f"  {format_rate(speed)}"
            else:
                text += "  measuring rate..."
            if current:
                text += f"  {current}"
        else:
            text = f"[*] Downloading packages... {format_bytes(downloaded)} received"
            if speed > 0:
                text += f"  {format_rate(speed)}"
            else:
                text += "  measuring rate..."
            if current:
                text += f"  {current}"
        self.status(text, time.monotonic())

    def install_status(self, done: int, total: int, current: str) -> None:
        if total > 0:
            fraction = min(done / total, 1.0)
            text = (
                f"[*] Installing {render_bar(fraction)} {fraction * 100:3.0f}%  "
                f"{done}/{total} packages"
            )
        else:
            text = f"[*] Installing packages... {done} complete"
        if current:
            text += f"  {current}"
        self.status(text, time.monotonic())

    def hook_status(self, done: int, total: int) -> None:
        if total > 0:
            fraction = min(done / total, 1.0)
            text = (
                f"[*] Post-transaction hooks {render_bar(fraction)} "
                f"{fraction * 100:3.0f}%  {done}/{total}"
            )
        else:
            text = f"[*] Running post-transaction hooks... {done} complete"
        self.status(text, time.monotonic())

    def slow_warning(self, speed: float, elapsed: float) -> None:
        if self.slow_warned or speed >= SLOW_RATE_BYTES or elapsed < 60:
            return
        self.slow_warned = True
        self.warn(
            f"download rate is {format_rate(speed)}; a large desktop can take "
            "hours. Set GRINTION_ALA_MIRRORS to a faster mirror if one is available."
        )

    def note_error(self, kind: str, message: str) -> None:
        entry = f"{kind}: {message}".strip()
        if entry not in self.seen_messages:
            self.seen_messages.add(entry)
            if kind.lower() == "warning":
                self.warnings.append(entry)
            else:
                self.errors.append(entry)

    def complete(
        self,
        plan: PacmanPlan | None,
        operation: str,
        elapsed: float,
        downloaded: int,
        skipped: bool,
    ) -> None:
        self.finish_status()
        if skipped:
            self.success("all requested packages are already installed and up to date")
            return
        if plan is not None:
            count = plan.total_packages
            if plan.unknown_size_count:
                detail = f"{count} package(s)"
            else:
                detail = (
                    f"{count} package(s), {format_bytes(plan.total_download)} download"
                )
        elif operation == "remove":
            detail = "removal complete"
        elif operation == "update":
            detail = "package databases updated"
        else:
            detail = "transaction complete"
        self.success(f"{detail} in {format_duration(elapsed)}")
        if downloaded > 0:
            self.header(f"Transferred {format_bytes(downloaded)}")

    def failure(
        self,
        rc: int,
        *,
        stalled: bool,
        stall_seconds: float,
        log_path: Path,
    ) -> None:
        self.finish_status()
        if stalled:
            self.warn(
                f"no download or installation progress for {format_duration(stall_seconds)}; "
                "stopped the stuck package manager"
            )
        self.error(f"package transaction failed (exit {rc})")
        for line in self.errors[:8]:
            self.warn(line)
        for line in self.warnings[:4]:
            self.warn(line)
        self.warn(f"full package manager log: {log_path}")


def run_transaction(
    argv: Sequence[str],
    *,
    root: str | Path = "/",
    log_path: str | Path | None = None,
    cache_dir: str | Path | None = None,
    stall_seconds: float | None = None,
    interval: float | None = None,
    quiet: bool | None = None,
    verbose: bool | None = None,
    stream: IO[str] | None = None,
) -> tuple[int, str]:
    """Run a package transaction and render Grintion's own progress UI.

    Returns the child exit status and the complete raw output. The raw output is
    still needed by callers that retry on pacman's exact file-conflict lines.
    """
    if not argv:
        raise ValueError("run_transaction requires a command")

    stream = stream or sys.stdout
    root_path = Path(root)
    cache_path = Path(cache_dir) if cache_dir is not None else cache_directory(argv, root_path)
    tty = bool(getattr(stream, "isatty", lambda: False)())
    if interval is None:
        interval = _env_float(
            "GRINTION_PROGRESS_INTERVAL", TTY_INTERVAL if tty else NON_TTY_INTERVAL
        )
    interval = max(interval, 0.1)
    if stall_seconds is None:
        stall_seconds = _env_float(
            "GRINTION_DOWNLOAD_STALL_SECONDS", DEFAULT_STALL_SECONDS
        )
    stall_seconds = max(stall_seconds, 0.0)
    if quiet is None:
        quiet = _env_flag("GRINTION_PROGRESS_QUIET")
    if verbose is None:
        verbose = _env_flag("GRINTION_PROGRESS_VERBOSE")

    operation = operation_of(argv)
    renderer = _Renderer(
        stream=stream,
        quiet=quiet,
        verbose=verbose,
        colored=color_enabled(stream),
        tty=tty,
        interval=interval,
    )
    if operation in ("install", "upgrade"):
        renderer.header("Resolving package transaction...")
    plan = build_plan(argv, root_path) if operation in ("install", "upgrade") else None

    log_target: Path
    temporary_log = False
    if log_path is None:
        descriptor, temporary = tempfile.mkstemp(
            prefix="grintion-package-", suffix=".log"
        )
        os.close(descriptor)
        log_target = Path(temporary)
        temporary_log = True
    else:
        log_target = Path(log_path)
        log_target.parent.mkdir(parents=True, exist_ok=True)
    log_handle = open(log_target, "w", encoding="utf-8", errors="replace")

    if verbose:
        renderer.header(f"Command: {' '.join(str(item) for item in argv)}")
    renderer.plan_summary(plan, operation)

    try:
        process = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, "LC_ALL": "C"},
        )
    except OSError as exc:
        log_handle.write(f"{exc}\n")
        log_handle.close()
        renderer.error(f"cannot start the package manager: {exc}")
        return 127, str(exc)

    line_queue: queue.Queue[str | None] = queue.Queue()
    raw_chunks: list[str] = []

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            raw_chunks.append(line)
            log_handle.write(line)
            log_handle.flush()
            line_queue.put(line)
        line_queue.put(None)

    reader_thread = threading.Thread(target=reader, name="pkg-progress-reader", daemon=True)
    reader_thread.start()

    started = time.monotonic()
    last_activity = started
    last_sample = started
    sync_dir = root_path / "var/lib/pacman/sync"
    last_sync_size = directory_size(sync_dir)
    initial_cache_size = directory_size(cache_path)
    initial_download = measured_download(plan, cache_path) if plan is not None else 0
    last_download = initial_download
    last_download_at = started
    speed = 0.0
    downloaded = initial_download
    install_done = 0
    install_total = plan.total_packages if plan is not None else 0
    current_package = ""
    hooks_done = 0
    hooks_total = 0
    stalled = False
    skipped = False
    nothing_to_do = False
    phase = "starting"
    update_phase = operation == "update"
    if operation == "remove":
        renderer.begin("remove", "Removing packages...")
    elif operation == "local":
        renderer.begin("local", "Installing local packages...")

    while True:
        try:
            item = line_queue.get(timeout=0.15)
        except queue.Empty:
            item = ""
        if item is None:
            break
        if item:
            text = item.rstrip("\n")
            renderer.raw(text)
            last_activity = time.monotonic()

            section = _SECTION_RE.match(text)
            if section is not None:
                label = section.group(1).strip()
                lowered = label.lower()
                if "synchronizing package databases" in lowered:
                    phase = "update"
                    renderer.begin("update", "Synchronizing package databases...")
                elif "retrieving packages" in lowered:
                    phase = "download"
                    renderer.begin("download", "Downloading packages...")
                elif "processing package changes" in lowered:
                    phase = "install"
                    renderer.begin("install", "Installing packages...")
                elif "running post-transaction hooks" in lowered:
                    phase = "hooks"
                    renderer.begin("hooks", "Running post-transaction hooks...")

            progress = _PROGRESS_RE.match(text)
            if progress is not None:
                done, total, action, package = progress.groups()
                if action.lower() == "removing":
                    phase = "remove"
                else:
                    phase = "install"
                install_done = int(done)
                install_total = max(install_total, int(total))
                current_package = package
                if phase == "remove":
                    renderer.begin("remove", "Removing packages...")
                else:
                    renderer.begin("install", "Installing packages...")
                last_activity = time.monotonic()
            else:
                hook = _HOOK_RE.match(text)
                if hook is not None and phase == "hooks":
                    hooks_done = int(hook.group(1))
                    hooks_total = max(hooks_total, int(hook.group(2)))

            download = _DOWNLOAD_RE.match(text)
            if download is not None:
                current_package = download.group(1)
                phase = "download"
                renderer.begin("download", "Downloading packages...")

            if "checking keyring" in text.lower():
                phase = "verify"
                renderer.begin("verify", "Verifying package signatures...")
            elif "checking package integrity" in text.lower():
                phase = "verify"
                renderer.begin("verify", "Checking package integrity...")
            elif "loading package files" in text.lower():
                phase = "load"
                renderer.begin("load", "Loading package files...")
            elif "checking for file conflicts" in text.lower():
                phase = "conflicts"
                renderer.begin("conflicts", "Checking for file conflicts...")

            error = _ERROR_RE.match(text)
            if error is not None:
                renderer.note_error(error.group(1).lower(), error.group(2))
            if "up to date -- skipping" in text:
                skipped = True
            if "there is nothing to do" in text.lower():
                nothing_to_do = True

        now = time.monotonic()
        if now - last_sample >= 0.25:
            # Track named package files first, then fall back to the cache
            # directory growing. The fallback keeps the counter (and the stall
            # watchdog) moving when the plan cannot name every file, for
            # example when a database sync changes a package version.
            sync_size = directory_size(sync_dir)
            if sync_size != last_sync_size:
                last_sync_size = sync_size
                last_activity = now
            downloaded = max(
                measured_download(plan, cache_path) if plan is not None else 0,
                max(0, directory_size(cache_path) - initial_cache_size),
            )
            if downloaded > last_download:
                last_activity = now
            elapsed_since_sample = now - last_download_at
            if elapsed_since_sample >= 0.5:
                instant = (downloaded - last_download) / elapsed_since_sample
                speed = instant if speed <= 0 else (speed * 0.7) + (instant * 0.3)
                last_download = downloaded
                last_download_at = now
            if phase == "download" or (
                downloaded > 0 and phase not in ("install", "hooks", "verify", "load", "conflicts")
            ):
                renderer.download_status(
                    downloaded,
                    plan.total_download if plan is not None else 0,
                    speed,
                    now - started,
                    current_package,
                    plan.unknown_size_count if plan is not None else 0,
                )
                renderer.slow_warning(speed, now - started)
            elif phase == "install":
                renderer.install_status(install_done, install_total, current_package)
            elif phase == "remove":
                renderer.install_status(install_done, install_total, current_package)
            elif phase == "hooks":
                renderer.hook_status(hooks_done, hooks_total)
            elif phase == "update" or update_phase:
                if now - renderer.last_status >= renderer.interval:
                    renderer.status("[*] Synchronizing package databases...", now)
            last_sample = now

        if stall_seconds > 0 and now - last_activity >= stall_seconds:
            stalled = True
            renderer.finish_status()
            renderer.warn(
                f"no download or installation progress for "
                f"{format_duration(stall_seconds)}; stopping the stuck package manager"
            )
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if clear_stale_pacman_lock(root_path):
                renderer.warn(f"removed stale pacman lock: {root_path / 'var/lib/pacman/db.lck'}")
            break

    if not stalled:
        rc = process.wait()
    else:
        rc = 124
    reader_thread.join(timeout=5)
    log_handle.close()
    renderer.finish_status()
    elapsed = time.monotonic() - started
    raw_output = "".join(raw_chunks)

    downloaded = max(
        measured_download(plan, cache_path) if plan is not None else 0,
        max(0, directory_size(cache_path) - initial_cache_size),
    )

    if rc == 0:
        renderer.complete(
            plan,
            operation,
            elapsed,
            max(downloaded - initial_download, 0),
            skipped or nothing_to_do,
        )
        for line in renderer.warnings[:4]:
            renderer.warn(line)
        if temporary_log:
            log_target.unlink(missing_ok=True)
    else:
        renderer.failure(
            rc,
            stalled=stalled,
            stall_seconds=stall_seconds,
            log_path=log_target,
        )
    return rc, raw_output


__all__ = [
    "PacmanPlan",
    "PlannedPackage",
    "build_plan",
    "clear_stale_pacman_lock",
    "directory_size",
    "format_bytes",
    "format_duration",
    "format_rate",
    "measured_download",
    "operation_of",
    "render_bar",
    "run_transaction",
]
