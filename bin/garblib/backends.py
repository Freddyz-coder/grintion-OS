"""Explicit, fail-closed delegation to pacman and apk."""
from __future__ import annotations

import argparse
import os
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .common import GarbError, log, warn

PACMAN_VERSION_RE = re.compile(r"Pacman v(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
APK_VERSION_RE = re.compile(r"apk-tools\s+(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)
SUPPORTED_BACKEND_MAJORS = {"pacman": frozenset({6, 7}), "apk": frozenset({2, 3})}
PROTECTED_OVERWRITE_PATHS = (
    "/etc/passwd",
    "/etc/passwd-",
    "/etc/shadow",
    "/etc/shadow-",
    "/etc/group",
    "/etc/group-",
    "/etc/gshadow",
    "/etc/gshadow-",
    "/etc/sudoers",
    "/etc/sudoers.d/",
    "/etc/ssh/ssh_host_",
    "/boot/",
    "/usr/lib/modules/",
)
MAX_OVERWRITE_CONFLICTS = 1024

# Names users know from other distributions, mapped to the package that
# provides the same thing in the pinned Arch snapshot. Arch package names are
# lowercase, so normalization alone fixes casing such as "NetworkManager".
PACMAN_PACKAGE_ALIASES = {
    "kde-plasma": "plasma-meta",
    "network-manager": "networkmanager",
}
PACMAN_SYNC_DB_COMMANDS = frozenset({"install", "search", "upgrade"})


def backend_kind(path: str) -> str:
    name = Path(path).name.lower()
    if "pacman" in name:
        return "pacman"
    if "apk" in name:
        return "apk"
    raise GarbError(f"GARB_BACKEND_BIN must point at pacman or apk, not: {path}")


def normalize_pacman_package(spec: str) -> str:
    """Map a user-facing package name to its Arch package name.

    Only bare names are rewritten. Local archive paths and relative paths are
    left alone; a version constraint keeps its ``name=version`` form.
    """
    name, separator, version = spec.partition("=")
    if not name or "/" in name or name.startswith(".") or name.startswith("-"):
        return spec
    normalized = PACMAN_PACKAGE_ALIASES.get(name.lower(), name.lower())
    return f"{normalized}{separator}{version}" if separator else normalized


def normalize_pacman_packages(packages: list[str]) -> list[str]:
    return [normalize_pacman_package(package) for package in packages]


def backend_version(backend: str, binary: str) -> tuple[int, int, int]:
    """Read and validate the external manager's version.

    The translator is written against pacman 6/7 and apk-tools 2/3. A future
    upstream release can keep the binary name while changing flags or database
    layout. Failing closed with an actionable message is safer than passing an
    unknown argument set to it.
    """
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GarbError(f"cannot read {backend} version from {binary}: {exc}") from exc
    text = f"{result.stdout}\n{result.stderr}"
    pattern = PACMAN_VERSION_RE if backend == "pacman" else APK_VERSION_RE
    match = pattern.search(text)
    if result.returncode != 0 or match is None:
        raise GarbError(
            f"{backend} at {binary} did not report a supported version; "
            "refusing to delegate (use --backend native after inspecting it)"
        )
    version = tuple(int(part) for part in match.groups())
    if version[0] not in SUPPORTED_BACKEND_MAJORS[backend]:
        supported = ", ".join(str(major) for major in sorted(SUPPORTED_BACKEND_MAJORS[backend]))
        raise GarbError(
            f"{backend} {version[0]}.{version[1]}.{version[2]} is outside the "
            f"verified translator range (supported major versions: {supported}); "
            "use --backend native or update garb before delegating"
        )
    return version


def external_backend_binary(requested: str) -> tuple[str, str] | None:
    """Return (backend, executable) for an explicit or auto-detected backend."""
    explicit = os.environ.get("GARB_BACKEND_BIN")
    names = [requested] if requested in ("pacman", "apk") else ["pacman", "apk"]
    if explicit:
        if not os.access(explicit, os.X_OK):
            raise GarbError(f"GARB_BACKEND_BIN is not executable: {explicit}")
        kind = backend_kind(explicit)
        if requested in ("pacman", "apk") and kind != requested:
            raise GarbError(
                f"GARB_BACKEND_BIN points at {kind}, but --backend {requested} was requested"
            )
        return kind, explicit
    for name in names:
        found = shutil.which(name)
        if found:
            return name, found
    return None


def _pacman_conf_repositories(root: Path) -> list[str]:
    """Return the repository sections configured for the target root."""
    try:
        text = (root / "etc/pacman.conf").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    repositories = []
    for line in text.splitlines():
        match = re.match(r"\s*\[([^\]]+)\]\s*$", line)
        if match is not None and match.group(1) != "options":
            repositories.append(match.group(1))
    return repositories


def pacman_databases_missing(root: Path) -> bool:
    """A fresh install has a local pacman database but no sync databases."""
    sync = root / "var/lib/pacman/sync"
    repositories = _pacman_conf_repositories(root)
    if not repositories:
        return not sync.is_dir() or not any(sync.glob("*.db"))
    return any(not (sync / f"{repository}.db").exists() for repository in repositories)


def sync_pacman_databases(binary: str, root: Path) -> None:
    """Download pacman's sync databases on a system that has none.

    The image ships the seeded local database but not the remote metadata.
    `pacman -S` without it prints "database file for 'core' does not exist" and
    then "target not found" for every package, which looks like a broken
    package manager. `garb update` remains available, but the first operation
    that needs remote metadata now performs it automatically.
    """
    if not pacman_databases_missing(root):
        return
    warn("package databases are missing; synchronizing them first (pacman -Sy)")
    argv = [binary]
    if str(root) != "/":
        argv += ["--root", str(root)]
    argv.append("-Sy")
    print(f"[garb] {' '.join(argv)}", file=sys.stderr)
    if subprocess.run(argv).returncode != 0:
        raise GarbError(
            "could not download the package databases; connect to the network "
            "and run 'sudo garb update' before installing packages"
        )


def select_pacman_mirror(root: Path) -> None:
    """Point the target's pinned pacman config at the fastest ALA endpoint.

    The selector is optional: a source-tree invocation of garb may not have
    the installed helper on PATH, and an offline system must still reach
    pacman's normal error path. Never make a package operation fail because
    the optimization could not run.
    """
    tool = shutil.which("grintion-pacman-mirror")
    if tool is None:
        return
    try:
        subprocess.run(
            [tool, "--quiet", "--root", str(root)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def external_argv(backend: str, binary: str, args: argparse.Namespace) -> list[str]:
    """Translate a garb command into the external manager's argument list."""
    root = Path(args.root)
    argv = [binary]
    if str(root) != "/":
        argv += ["--root", str(root)]

    command = args.command
    if backend == "pacman":
        if command == "update":
            if getattr(args, "key", None) or getattr(args, "allow_unsigned", False):
                raise GarbError("--key/--allow-unsigned are native-garb options")
            argv.append("-Sy")
        elif command == "search":
            argv += ["-Ss", args.query]
        elif command == "info":
            argv += [
                "-Qi" if getattr(args, "installed", False) else "-Si",
                normalize_pacman_package(args.package),
            ]
        elif command == "install":
            if args.force:
                raise GarbError("--force is not supported by the pacman backend")
            # `pacman -S` on an installed, current package prints
            # "warning: <pkg> is up to date -- reinstalling" and rewrites it.
            # `garb install` means "make sure it is present", so let pacman
            # skip packages that are already installed. `garb upgrade` (or
            # `garb install --upgrade`) is the explicit reinstall/upgrade path.
            argv.append("-S")
            if not getattr(args, "upgrade", False):
                argv.append("--needed")
            argv += ["--noconfirm", *normalize_pacman_packages(args.package)]
        elif command == "remove":
            if args.force:
                raise GarbError("--force is not supported by the pacman backend")
            argv += ["-R", "--noconfirm", *normalize_pacman_packages(args.package)]
        elif command == "verify":
            if getattr(args, "format", "text") != "text":
                raise GarbError("--format json is a native-garb option")
            argv.append("-Qk" if args.quick else "-Qkk")
            argv += normalize_pacman_packages(args.package)
        elif command == "upgrade":
            if args.package:
                argv += ["-S", "--noconfirm", *normalize_pacman_packages(args.package)]
            else:
                argv += ["-Su", "--noconfirm"]
        else:
            raise GarbError(f"pacman has no mapping for garb {command}")
        return argv

    if command == "update":
        if getattr(args, "key", None) or getattr(args, "allow_unsigned", False):
            raise GarbError("--key/--allow-unsigned are native-garb options")
        argv.append("update")
    elif command == "search":
        argv += ["search", args.query]
    elif command == "info":
        argv += ["info", args.package]
    elif command == "install":
        if args.force:
            raise GarbError("--force is not supported by the apk backend")
        argv += ["add", *args.package]
    elif command == "remove":
        if args.force:
            raise GarbError("--force is not supported by the apk backend")
        argv += ["del", *args.package]
    elif command == "verify":
        if args.quick:
            raise GarbError("--quick is not supported by the apk backend")
        if getattr(args, "format", "text") != "text":
            raise GarbError("--format json is a native-garb option")
        argv += ["audit", *args.package]
    elif command == "upgrade":
        argv += ["upgrade", *args.package]
    else:
        raise GarbError(f"apk has no mapping for garb {command}")
    return argv


def conflict_paths(output: str) -> list[str]:
    paths = set()
    for line in output.splitlines():
        # pacman 6 prints "path exists in filesystem". pacman 7 prints
        # "package: path exists in filesystem" (or, in some builds,
        # "path: exists in filesystem"). The optional group is the package
        # prefix; the path is always the token before "exists".
        match = re.match(
            r"^\s*(?:(\S+):\s+)?(\S+)\s+exists in filesystem\b", line
        )
        if match is None:
            continue
        path = match.group(2).rstrip(":")
        paths.add(posixpath.normpath("/" + path.lstrip("/")))
    return sorted(paths)


def protected_overwrite(path: str) -> bool:
    normalized = posixpath.normpath(path)
    for protected in PROTECTED_OVERWRITE_PATHS:
        if normalized == protected or normalized.startswith(protected):
            return True
    return False


def run_streaming(argv: list[str]) -> tuple[int, str]:
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    chunks: list[str] = []
    for line in process.stdout:
        chunks.append(line)
        print(line, end="", flush=True)
    return process.wait(), "".join(chunks)


def _repair_mtab(root: Path) -> None:
    """Repair the mount table pacman's CheckSpace reads before delegation.

    Arch and Grintion expect /etc/mtab to point at /proc/self/mounts. A regular
    or stale file makes pacman fail with "could not open file: /etc/mtab:
    Permission denied" and aborts before the transaction. Running as root is
    already required, so restore the canonical symlink instead of asking the
    user to debug a file that the image owns.
    """
    mtab = root / "etc/mtab"
    expected = "/proc/self/mounts"
    try:
        if mtab.is_symlink() and os.readlink(mtab) == expected:
            return
        if mtab.exists() or mtab.is_symlink():
            mtab.unlink()
        mtab.parent.mkdir(parents=True, exist_ok=True)
        mtab.symlink_to(expected)
        warn("repaired /etc/mtab -> /proc/self/mounts before pacman")
    except OSError as exc:
        raise GarbError(
            f"cannot repair {mtab}: {exc}; create it with: "
            "ln -sfn /proc/self/mounts /etc/mtab"
        ) from exc


def run_external_backend(backend: str, binary: str, args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if root == Path("/") and os.geteuid() != 0:
        packages = " ".join(getattr(args, "package", []) or [])
        raise GarbError(
            "package transactions on / require root; rerun with: sudo garb "
            f"{args.command} {packages}".rstrip()
        )
    if backend == "pacman" and getattr(args, "command", "") in ("install", "remove", "upgrade"):
        _repair_mtab(root)
    if backend == "pacman" and getattr(args, "command", "") in (
        "install",
        "update",
        "upgrade",
    ):
        select_pacman_mirror(root)
    if backend == "pacman" and (
        getattr(args, "command", "") in PACMAN_SYNC_DB_COMMANDS
        or (
            getattr(args, "command", "") == "info"
            and not getattr(args, "installed", False)
        )
    ):
        sync_pacman_databases(binary, root)
    argv = external_argv(backend, binary, args)
    warn(f"using the {backend} backend; garb signature and transaction checks do not apply")
    print(f"[garb] {' '.join(argv)}", file=sys.stderr)

    # Never pass a blanket --overwrite '*'. It lets an upstream package replace
    # account, sudo, SSH host-key or boot files. Retry only the exact paths the
    # transaction reported, and refuse the security-sensitive ones outright.
    if backend != "pacman" or args.command not in ("install", "upgrade"):
        return subprocess.run(argv).returncode
    rc, output = run_streaming(argv)
    if rc == 0:
        if (
            backend == "pacman"
            and args.command == "install"
            and "--needed" in argv
            and "up to date -- skipping" in output
        ):
            log(
                "all requested packages are already installed and up to date; "
                "nothing to do (use 'garb upgrade' to reinstall)"
            )
        return 0
    missing = sorted(set(re.findall(r"^error: target not found:\s*(\S+)", output, re.MULTILINE)))
    if missing:
        warn("pacman could not find: " + ", ".join(missing))
        warn(
            "check the name with 'garb search <name>'; desktop environments "
            "install with 'sudo grintion-desktop install kde' (or xfce, lxqt, sway, i3)"
        )
    conflicts = conflict_paths(output)
    if not conflicts:
        return rc
    protected = [path for path in conflicts if protected_overwrite(path)]
    if protected:
        raise GarbError(
            "refusing to overwrite security-sensitive path(s): "
            + ", ".join(protected[:8])
        )
    if len(conflicts) > MAX_OVERWRITE_CONFLICTS:
        raise GarbError(
            f"{len(conflicts)} file conflicts reported; refusing a blanket overwrite. "
            "Use --backend native or remove the conflicting files first"
        )
    retry = list(argv)
    for path in conflicts:
        retry += ["--overwrite", path, "--overwrite", path.lstrip("/")]
    warn(
        f"retrying with overwrite limited to {len(conflicts)} reported conflict path(s); "
        "security-sensitive paths remain protected"
    )
    print(f"[garb] {' '.join(retry)}", file=sys.stderr)
    retry_rc, _ = run_streaming(retry)
    return retry_rc
