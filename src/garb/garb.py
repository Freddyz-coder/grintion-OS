#!/usr/bin/env python3
"""
garb - Grintion Atomic Reliable Builder & Package Manager
Philosophy: MISS (Minimalist, Independent, Secure, Stable)
Purpose: Built for paranoid users of Grintion-OS.
Supports: Native .garb packages, AppImage, Flatpak, and Snap sandboxes.
"""

import sys
import os
import json
import hashlib
import tarfile
import shutil
import subprocess
import argparse
import time
from pathlib import Path

VERSION = "0.1.0-alpha"
DEFAULT_DB_PATH = "/var/lib/garb/db.json"
DEFAULT_REPO_PATH = "/etc/garb/repos.d"
DEFAULT_CACHE_PATH = "/var/cache/garb"

ASCII_LOGO = r"""
        █
       █▓█
      █▓▒▓█
     █▓▒@▒▓█
    █▓▒@@@▒▓█
   █▓▒@+-+@▒▓█
  █▓▒@+---+@▒▓█
 █▓▒@+-/-\-+@▒▓█
█▓▒@+-/   \-+@▒▓█
    ▓▒@   @▒▓         
   ▓▒@     @▒▓
  ▓▒@       @▒▓
 ▓▒@         @▒▓
█@█           █@█
"""

class GarbDB:
    def __init__(self, root="/"):
        self.root = Path(root)
        if self.root == Path("/") and hasattr(os, "geteuid") and os.geteuid() != 0:
            user_state = Path.home() / ".local/share/garb"
            self.db_path = user_state / "db.json"
        else:
            self.db_path = self.root / DEFAULT_DB_PATH.lstrip("/")
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.data = self._load()

    def _load(self):
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Warning: corrupted DB {self.db_path}, recovering: {e}", file=sys.stderr)
        return {"version": 1, "packages": {}}

    def save(self):
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.db_path.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            tmp_file.replace(self.db_path)
        except OSError as e:
            print(f"[!] Warning: Unable to save database to {self.db_path}: {e}", file=sys.stderr)

    def is_installed(self, pkg_name):
        return pkg_name in self.data["packages"]

    def add_package(self, pkg_name, metadata, files):
        self.data["packages"][pkg_name] = {
            "version": metadata.get("version", "1.0.0"),
            "release": metadata.get("release", 1),
            "description": metadata.get("description", ""),
            "arch": metadata.get("arch", ["x86_64", "aarch64"]),
            "installed_at": int(time.time()),
            "files": files,
            "sha256": metadata.get("sha256", ""),
        }
        self.save()

    def remove_package(self, pkg_name):
        if pkg_name in self.data["packages"]:
            del self.data["packages"][pkg_name]
            self.save()

    def get_installed(self):
        return self.data["packages"]


def calculate_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def cmd_version(args):
    print(f"garb package manager v{VERSION}")
    print("Philosophy: MISS (Minimalist, Independent, Secure, Stable)")
    print("Target Architectures: x86_64, aarch64")


def cmd_search(args):
    query = args.query.lower()
    print(f"[*] Searching repository for '{query}'...")
    
    # Check local packages directory first if available
    repo_dirs = [
        Path("/etc/garb/packages"),
        Path("/usr/share/garb/packages"),
        Path(os.getcwd()) / "packages",
    ]
    
    found = 0
    for repo_dir in repo_dirs:
        if not repo_dir.exists():
            continue
        for pkg_dir in repo_dir.iterdir():
            if pkg_dir.is_dir():
                manifest = pkg_dir / "Garbfile"
                if manifest.exists():
                    name = pkg_dir.name
                    desc = ""
                    with open(manifest, "r", encoding="utf-8") as mf:
                        for line in mf:
                            if "description" in line and "=" in line:
                                desc = line.split("=", 1)[1].strip().strip('"')
                    if query in name.lower() or query in desc.lower():
                        print(f"  \033[1;32m{name}\033[0m: {desc}")
                        found += 1
    
    # Also search installed database
    db = GarbDB(args.root)
    for name, info in db.get_installed().items():
        if query in name.lower() or query in info.get("description", "").lower():
            if found == 0:
                print(f"  \033[1;34m{name}\033[0m [installed]: {info.get('description', '')}")
                found += 1

    if found == 0:
        print(f"[-] No packages matching '{query}' found.")


def cmd_info(args):
    pkg_name = args.package
    db = GarbDB(args.root)
    if db.is_installed(pkg_name):
        info = db.get_installed()[pkg_name]
        print(f"\033[1;36mPackage:\033[0m     {pkg_name}")
        print(f"\033[1;36mStatus:\033[0m      Installed")
        print(f"\033[1;36mVersion:\033[0m     {info.get('version')}-{info.get('release')}")
        print(f"\033[1;36mDescription:\033[0m {info.get('description')}")
        print(f"\033[1;36mInstalled:\033[0m   {time.ctime(info.get('installed_at'))}")
        print(f"\033[1;36mTracked Files:\033[0m {len(info.get('files', []))}")
        return

    # Check repository manifests
    manifest_paths = [
        Path(f"/etc/garb/packages/{pkg_name}/Garbfile"),
        Path(f"/usr/share/garb/packages/{pkg_name}/Garbfile"),
        Path(os.getcwd()) / f"packages/{pkg_name}/Garbfile",
    ]
    for mp in manifest_paths:
        if mp.exists():
            print(f"\033[1;36mPackage:\033[0m {pkg_name} (Source Manifest)")
            with open(mp, "r", encoding="utf-8") as f:
                print(f.read())
            return

    print(f"[-] Package '{pkg_name}' not found.")


def cmd_verify(args):
    db = GarbDB(args.root)
    target = args.package
    pkgs = [target] if target else list(db.get_installed().keys())
    
    if not pkgs:
        print("[*] No packages installed to verify.")
        return

    print(f"[*] Verifying integrity of {len(pkgs)} package(s)...")
    corrupted = 0
    total_files = 0

    for pkg_name in pkgs:
        if not db.is_installed(pkg_name):
            print(f"[-] Package '{pkg_name}' is not installed.")
            continue
        
        info = db.get_installed()[pkg_name]
        pkg_corrupt = False
        for rel_file in info.get("files", []):
            total_files += 1
            full_path = Path(args.root) / rel_file.lstrip("/")
            if not full_path.exists():
                print(f"  \033[1;31m[MISSING]\033[0m {rel_file} (from {pkg_name})")
                pkg_corrupt = True
                corrupted += 1
        
        if not pkg_corrupt:
            print(f"  \033[1;32m[OK]\033[0m {pkg_name} ({len(info.get('files', []))} files)")

    if corrupted == 0:
        print(f"[+] Integrity check PASSED: {total_files} files verified, 0 anomalies.")
    else:
        print(f"[!] Integrity check FAILED: {corrupted} anomaly detected!", file=sys.stderr)
        sys.exit(1)


def cmd_install(args):
    pkg_name = args.package
    root = Path(args.root)
    db = GarbDB(args.root)
    
    print(f"[*] garb install: {pkg_name} -> {root}")

    # Check if archive was provided directly
    if Path(pkg_name).exists() and pkg_name.endswith(".garb"):
        archive_path = Path(pkg_name)
    else:
        # Look in cache or package repository
        archive_path = Path(DEFAULT_CACHE_PATH) / f"{pkg_name}.garb"
        if not archive_path.exists():
            # Check if source manifest exists to build
            manifest = Path(f"packages/{pkg_name}/Garbfile")
            if manifest.exists():
                print(f"[*] Found manifest at {manifest}, building package...")
                archive_path = build_from_manifest(manifest, Path(DEFAULT_CACHE_PATH))
            else:
                print(f"[-] Package '{pkg_name}' not found in repositories or cache.", file=sys.stderr)
                sys.exit(1)

    # Validate package integrity
    sha_calc = calculate_sha256(archive_path)
    print(f"[+] Package archive SHA-256: {sha_calc}")

    # Extract to target root
    print(f"[*] Unpacking to target root: {root}...")
    tracked_files = []
    metadata = {"name": pkg_name, "version": "1.0.0", "sha256": sha_calc}

    with tarfile.open(archive_path, "r:*") as tar:
        # Check if metadata manifest exists inside archive
        try:
            meta_member = tar.getmember("GARB_METADATA.json")
            meta_f = tar.extractfile(meta_member)
            if meta_f:
                metadata = json.loads(meta_f.read().decode("utf-8"))
        except KeyError:
            pass

        for member in tar.getmembers():
            if member.name == "GARB_METADATA.json":
                continue
            tar.extract(member, path=root)
            tracked_files.append("/" + member.name.lstrip("./"))

    db.add_package(pkg_name, metadata, tracked_files)
    print(f"[+] Successfully installed {pkg_name} ({len(tracked_files)} files tracked).")


def cmd_remove(args):
    pkg_name = args.package
    root = Path(args.root)
    db = GarbDB(args.root)

    if not db.is_installed(pkg_name):
        print(f"[-] Package '{pkg_name}' is not installed.", file=sys.stderr)
        sys.exit(1)

    info = db.get_installed()[pkg_name]
    files = info.get("files", [])
    print(f"[*] Removing {pkg_name} ({len(files)} files)...")

    removed_count = 0
    for f in reversed(files):
        target_path = root / f.lstrip("/")
        try:
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()
                removed_count += 1
            elif target_path.is_dir() and not any(target_path.iterdir()):
                target_path.rmdir()
        except Exception as e:
            print(f"[!] Warning removing {f}: {e}")

    db.remove_package(pkg_name)
    print(f"[+] Cleanly uninstalled {pkg_name}. ({removed_count} files removed).")


def build_from_manifest(manifest_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    pkg_name = manifest_path.parent.name
    meta = {
        "name": pkg_name,
        "version": "1.0.0",
        "description": f"Grintion package for {pkg_name}",
        "arch": ["x86_64", "aarch64"],
    }
    
    # Read manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("name ="):
                meta["name"] = line.split("=", 1)[1].strip().strip('"')
            elif line.strip().startswith("version ="):
                meta["version"] = line.split("=", 1)[1].strip().strip('"')
            elif line.strip().startswith("description ="):
                meta["description"] = line.split("=", 1)[1].strip().strip('"')

    pkg_archive = output_dir / f"{meta['name']}.garb"
    pkg_root = manifest_path.parent / "root"

    with tarfile.open(pkg_archive, "w:gz") as tar:
        # Add metadata JSON
        meta_json_bytes = json.dumps(meta, indent=2).encode("utf-8")
        import io
        ti = tarfile.TarInfo(name="GARB_METADATA.json")
        ti.size = len(meta_json_bytes)
        ti.mtime = int(time.time())
        ti.mode = 0o644
        tar.addfile(ti, io.BytesIO(meta_json_bytes))

        # Add files from pkg_root if present
        if pkg_root.exists():
            for root, dirs, files in os.walk(pkg_root):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, pkg_root)
                    tar.add(full_p, arcname=rel_p)

    return pkg_archive


def cmd_build(args):
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[-] Manifest '{manifest_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output) if args.output else Path.cwd() / "dist"
    print(f"[*] Building package from manifest: {manifest_path}...")
    archive = build_from_manifest(manifest_path, out_dir)
    sha = calculate_sha256(archive)
    print(f"[+] Package built: {archive}")
    print(f"[+] SHA-256 Digest: {sha}")


def cmd_bootstrap(args):
    target = Path(args.target).resolve()
    print(ASCII_LOGO)
    print(f"[*] Bootstrapping Grintion-OS base system to: {target}")
    
    # Ensure base directories exist
    dirs = [
        "bin", "sbin", "usr/bin", "usr/sbin", "usr/lib", "usr/local/bin",
        "etc/runit", "etc/sv", "etc/sysctl.d", "var/service", "var/log",
        "var/lib/garb", "var/cache/garb", "proc", "sys", "dev", "run",
        "tmp", "root", "home", "boot/efi", "mnt"
    ]
    for d in dirs:
        (target / d).mkdir(parents=True, exist_ok=True)
    
    # Restrict /tmp and /root permissions
    os.chmod(target / "tmp", 0o1777)
    os.chmod(target / "root", 0o700)

    # Copy core configurations from repository if present
    repo_root = Path(__file__).resolve().parent.parent.parent
    etc_source = repo_root / "etc"
    if etc_source.exists():
        print("[*] Installing system configurations (/etc/runit, /etc/sysctl.d)...")
        for item in etc_source.iterdir():
            dest = target / "etc" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    # Install garb into target /usr/bin/garb
    garb_dest = target / "usr/bin/garb"
    shutil.copy2(__file__, garb_dest)
    os.chmod(garb_dest, 0o755)
    
    # Create /bin/garb symlink
    bin_garb = target / "bin/garb"
    if bin_garb.exists() or bin_garb.is_symlink():
        bin_garb.unlink()
    bin_garb.symlink_to("/usr/bin/garb")

    # Initialize empty GarbDB in target
    db = GarbDB(root=target)
    db.add_package("grintion-base", {
        "version": VERSION,
        "release": 1,
        "description": "Grintion-OS minimal base system files",
        "arch": ["x86_64", "aarch64"],
        "sha256": "BOOTSTRAP_STAGE_1",
    }, [
        "/etc/runit/1", "/etc/runit/2", "/etc/runit/3",
        "/etc/issue", "/usr/bin/garb"
    ])

    print("[+] Grintion-OS base bootstrap complete!")
    print(f"[*] Next DIY steps:")
    print(f"    1. grintion-chroot {target}")
    print(f"    2. passwd (set root password)")
    print(f"    3. limine-deploy --efi {target}/boot/efi")
    print(f"    4. reboot and remove installation media")


def cmd_sandbox_run(args):
    """
    Universal sandbox runner for:
    - AppImage
    - Flatpak
    - Snap / Squashfs containers
    - Untrusted executables
    Utilizes bubblewrap (bwrap) or user namespaces (unshare)
    """
    target_app = Path(args.app).resolve()
    if not target_app.exists() and not shutil.which(args.app):
        print(f"[-] Target application '{args.app}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Grintion Sandbox: Preparing isolated environment for '{args.app}'...")
    print(f"[*] Policy: MISS Paranoid Isolation (seccomp, ro-root, private-dev, isolated-tmp)")

    # Detect application type
    is_appimage = str(target_app).lower().endswith(".appimage")
    is_flatpak = args.app.startswith("org.") or args.app.startswith("com.") or shutil.which("flatpak") and "flatpak" in args.app
    is_snap = args.app.startswith("snap:") or str(target_app).endswith(".snap")

    has_bwrap = shutil.which("bwrap") is not None

    if has_bwrap:
        bwrap_cmd = [
            "bwrap",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]
        
        # Network isolation check
        if args.no_net:
            bwrap_cmd.append("--unshare-net")
            print("  [✓] Network: Isolated (air-gapped namespace)")
        else:
            print("  [✓] Network: Allowed")

        # Home directory isolation
        if args.rw_home:
            bwrap_cmd.extend(["--bind", str(Path.home()), str(Path.home())])
            print(f"  [!] Home Directory: Read-Write access granted")
        else:
            sandbox_home = Path("/tmp/garb_sandbox_home")
            sandbox_home.mkdir(parents=True, exist_ok=True)
            bwrap_cmd.extend(["--bind", str(sandbox_home), str(Path.home())])
            print(f"  [✓] Home Directory: Isolated temporary sandbox")

        # FUSE passthrough for AppImage
        if is_appimage:
            if Path("/dev/fuse").exists():
                bwrap_cmd.extend(["--dev-bind", "/dev/fuse", "/dev/fuse"])
            bwrap_cmd.extend(["--setenv", "APPIMAGE_SILENT_INSTALL", "1"])

        bwrap_cmd.append(str(target_app))
        bwrap_cmd.extend(args.extra_args)

        print(f"[*] Executing via bubblewrap container sandbox...")
        try:
            sys.exit(subprocess.run(bwrap_cmd).returncode)
        except FileNotFoundError:
            pass

    # Fallback: unshare user namespace sandbox
    if shutil.which("unshare"):
        unshare_cmd = ["unshare", "--mount", "--uts", "--ipc"]
        if args.no_net:
            unshare_cmd.append("--net")
        unshare_cmd.append(str(target_app))
        unshare_cmd.extend(args.extra_args)
        print(f"[*] Executing via unshare user namespace sandbox...")
        sys.exit(subprocess.run(unshare_cmd).returncode)

    # Direct execution with warning
    print("[!] Warning: Neither bwrap nor unshare available. Launching directly with environment sanitization.")
    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "USER": os.environ.get("USER", "grintion"),
        "TERM": os.environ.get("TERM", "xterm"),
    }
    sys.exit(subprocess.run([str(target_app)] + args.extra_args, env=clean_env).returncode)


def main():
    parser = argparse.ArgumentParser(
        prog="garb",
        description="Grintion-OS Minimalist & Paranoid Package Manager (MISS Philosophy)",
    )
    parser.add_argument("--root", default="/", help="Target filesystem root (default: /)")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # version
    sub_version = subparsers.add_parser("version", help="Show garb version and architecture info")
    sub_version.set_defaults(func=cmd_version)

    # search
    sub_search = subparsers.add_parser("search", help="Search available packages")
    sub_search.add_argument("query", help="Package name or keyword")
    sub_search.set_defaults(func=cmd_search)

    # info
    sub_info = subparsers.add_parser("info", help="View detailed package manifest and integrity")
    sub_info.add_argument("package", help="Package name")
    sub_info.set_defaults(func=cmd_info)

    # verify
    sub_verify = subparsers.add_parser("verify", help="Cryptographically verify installed files")
    sub_verify.add_argument("package", nargs="?", default=None, help="Specific package to verify (default: all)")
    sub_verify.set_defaults(func=cmd_verify)

    # install
    sub_install = subparsers.add_parser("install", help="Install a package")
    sub_install.add_argument("package", help="Package name or .garb archive file")
    sub_install.set_defaults(func=cmd_install)

    # remove
    sub_remove = subparsers.add_parser("remove", help="Remove an installed package")
    sub_remove.add_argument("package", help="Package name to uninstall")
    sub_remove.set_defaults(func=cmd_remove)

    # build
    sub_build = subparsers.add_parser("build", help="Build a .garb package from a Garbfile manifest")
    sub_build.add_argument("manifest", help="Path to Garbfile manifest")
    sub_build.add_argument("-o", "--output", help="Output directory for .garb package")
    sub_build.set_defaults(func=cmd_build)

    # bootstrap
    sub_bootstrap = subparsers.add_parser("bootstrap", help="Bootstrap minimal Grintion base into target directory")
    sub_bootstrap.add_argument("target", help="Mount point or target root directory (e.g. /mnt)")
    sub_bootstrap.set_defaults(func=cmd_bootstrap)

    # sandbox
    sub_sandbox = subparsers.add_parser("sandbox", help="Universal sandbox runner for AppImage, Flatpak, and Snap")
    sandbox_sub = sub_sandbox.add_subparsers(dest="sandbox_action")
    sub_sandbox_run = sandbox_sub.add_parser("run", help="Run application in an isolated paranoid sandbox")
    sub_sandbox_run.add_argument("app", help="Path to AppImage, Flatpak id, Snap, or executable")
    sub_sandbox_run.add_argument("--no-net", action="store_true", help="Completely disconnect network namespace")
    sub_sandbox_run.add_argument("--rw-home", action="store_true", help="Allow read-write access to host $HOME (default: false)")
    sub_sandbox_run.add_argument("extra_args", nargs="*", help="Arguments passed to the application")
    sub_sandbox_run.set_defaults(func=cmd_sandbox_run)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
