# Changelog

All notable changes to **Grintion-OS** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-alpha] - 2026-10-28

### Added
- **Core Architecture & Identity**:
  - Independent OS specification directly on vanilla Linux kernel (zero distribution dependencies).
  - Adopted the **MISS** philosophy: Minimalist, Independent, Secure, and Stable.
  - Official ASCII emblem integrated into boot banners, console issues, and documentation.
  - Multi-architecture support for `x86_64` and `aarch64` (ARM64).

- **The `garb` Package Manager**:
  - Core command-line interface supporting `install`, `remove`, `update`, `search`, `verify`, and `bootstrap`.
  - Cryptographic verification of packages using SHA-256 and digital signatures.
  - Human-readable declarative `Garbfile` package manifest format.
  - Integrated container and sandbox manager supporting **Flatpak**, **Snap**, and **AppImage** formats via kernel user namespaces, cgroups v2, and bubblewrap.

- **Init System (`runit`)**:
  - 3-stage init lifecycle implementation:
    - `/etc/runit/1`: Early boot, essential virtual filesystem mounts (`/proc`, `/sys`, `/dev`, `/dev/pts`, `/dev/shm`), cgroups v2, entropy seeding, and paranoid kernel `sysctl` security lockdown.
    - `/etc/runit/2`: Dynamic service supervision via `runsvdir` managing `/var/service`.
    - `/etc/runit/3`: Clean shutdown, graceful service stopping, cache flushing, unmounting filesystems, and anti-forensic memory scrubbing.
  - Essential supervision services: virtual terminal getty daemons (`agetty-tty1` through `tty4`), minimal syslog, and network link daemon.

- **Userland & Core Utilities**:
  - Direct integration with GNU coreutils (`ls`, `cat`, `chmod`, `dd`, `chroot`, etc.).
  - Default secure shells and standard POSIX-compliant hierarchy.

- **Live RAM & DIY Environment**:
  - Live RAM image running completely in `tmpfs` without touching physical storage until explicitly directed.
  - Interactive DIY welcome prompt and `grintion-install` / `diy-guide` tools to assist paranoid users in manual partitioning, formatting, bootstrapping, driver setup, and bootloader installation.

- **ISO Build Pipeline**:
  - Local reproducible ISO build system using Limine bootloader (dual BIOS + UEFI El Torito hybrid) and `xorriso`.
  - Generates bootable `grintion-os-x86_64.iso` image directly.

- **Documentation**:
  - `README.md` with full philosophy, architecture details, and DIY workflow walkthrough.
  - `SECURITY.md` detailing the paranoid threat model, kernel hardening parameters, sandbox isolation, and reporting procedures.
  - `CONTRIBUTING.md` defining code conventions, `garb` packaging guidelines, and review standards.
  - `LICENSE` / `LICENSE.md` outlining licensing terms.

---

## [Planned / Roadmap]

### Planned for v0.2.0-beta
- Multi-arch automated ARM64 ISO/raw image generation pipeline.
- Hardware cryptographic token support (YubiKey / Nitrokey) integrated directly into `runit` stage 1 disk unlocking.
- Zero-leak RAM wiping daemon utilizing `kexec` and secure memory zeroing before warm reboot.
- Pre-built repository mirrors with BLAKE3 cryptographic ledger.
