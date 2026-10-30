# Changelog

All notable changes to **Grintion-OS** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.1-alpha] - 2026-10-30

### Fixed
- **Production Readiness Overhaul**:
  - Expanded rootfs binary list from ~70 to **120+ commands** — every command a user would expect now works.
  - Added missing binaries: `clear`, `reset`, `tput`, `ssh`, `scp`, `sftp`, `ssh-keygen`, `ssh-agent`, `whoami`, `groups`, `pgrep`, `pkill`, `watch`, `nc`, `ifconfig`, `route`, `wpa_passphrase`, `vim`, `zip`, `fsck`, `mkswap`, `lscpu`, `fuser`, `lsof`, `hexdump`, `stty`, `expr`, `seq`, `nice`, `nohup`, `flock`, `timeout`, and many more.
  - Build script now **reports missing binaries** instead of silently skipping them.

- **Terminal Support**:
  - Deployed terminfo database (`/usr/share/terminfo/`) — fixes `clear`, `reset`, `tput`, `nano`, `vi`, and all terminal-aware programs.

- **sudo**:
  - Added `/etc/sudoers` with `wheel` group support and secure defaults — `sudo` now works properly.

- **SSH**:
  - Added `/etc/ssh/ssh_config` with sane client defaults — `ssh`, `scp`, `sftp` now work out of the box.

- **System Infrastructure**:
  - Added `/etc/nsswitch.conf` — fixes user/group lookups (`getent`, `whoami`) and DNS resolution.
  - Added `/etc/os-release` — fastfetch and system tools now correctly identify "Grintion-OS 0.2.0-alpha (MISS)".
  - Added `/etc/shells` — proper login shell validation.

---

## [0.2.0-alpha] - 2026-10-30

### Added
- **Networking Stack**:
  - `dhcpcd` DHCP client with automatic runit service for wired networks.
  - `wpa_supplicant` + `wpa_cli` + `iw` for WiFi support with runit service (`etc/sv/wpa_supplicant`).
  - `curl`, `wget`, `ping`, `ss`, `dig`, `nslookup`, `rfkill` included in live rootfs.
  - Default DNS resolver (`/etc/resolv.conf`) pre-configured with Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`).
  - Improved `etc/sv/network/run` with interface readiness delay and better `dhcpcd` flags.

- **Expanded Linux Commands** (50+ new binaries in rootfs):
  - Process monitoring: `ps`, `top`, `htop`, `kill`, `killall`, `free`, `dmesg`, `uptime`.
  - User management: `passwd`, `useradd`, `userdel`, `groupadd`, `groupdel`, `su`, `sudo`, `chpasswd`.
  - Editors & pagers: `nano`, `vi`, `less`, `more`.
  - Kernel modules: `lsmod`, `modprobe`, `insmod`, `rmmod`, `depmod`, `modinfo`.
  - Hardware info: `lspci`, `lsusb`, `lsblk`.
  - Text processing: `wc`, `sort`, `uniq`, `tr`, `cut`, `tee`, `xargs`, `file`, `which`, `diff`.
  - System control: `hostname`, `reboot`, `poweroff`, `halt`, `shutdown`, `sysctl`.
  - Archiving: `bzip2`, `xz`, `unzip`, `cpio`.

- **Driver Support Infrastructure**:
  - Kernel module loading tools (`modprobe`, `insmod`, `lsmod`, `depmod`) in live rootfs.
  - Automatic kernel module deployment during rootfs build (network, GPU, USB, HID, NVMe, SCSI, SATA, filesystem, sound).
  - Module autoloading on boot via runit stage 1 (usbhid, ahci, nvme, sd_mod, ext4, vfat).
  - Udev-less coldplug device detection via sysfs uevent triggering.
  - New garb packages: `linux-firmware`, `mesa`, `alsa-lib`, `alsa-utils`.

- **Fastfetch Integration**:
  - Grintion-OS ASCII logo displayed via `fastfetch` on login with system information.
  - Custom configuration at `/etc/fastfetch/config.jsonc`.
  - Logo art stored at `/etc/grintion-logo.txt`.
  - Falls back to `/etc/issue` if fastfetch is not installed.

- **Desktop Environment / Window Manager / Login Manager Support** (via garb):
  - New garb package manifests (Garbfiles) for user-installable graphical environments:
    - Display servers: `xorg-server`, `xorg-xinit`, `wayland`
    - Login manager: `sddm` (with runit service at `etc/sv/sddm`)
    - Window managers: `i3`, `sway`, `openbox`
    - Desktop environments: `xfce4`, `plasma-desktop`
  - Nothing pre-installed — fully DIY per MISS philosophy.

- **Networking garb package** (`packages/networking/Garbfile`): meta-package for core networking stack.

### Improved
- **`grintion-install`**:
  - Now copies kernel and initramfs to installed system's `/boot`.
  - Added EFI partition entry to generated `/etc/fstab`.
  - Renumbered installation steps (4→7 steps for clarity).

- **`grintion-persist`**:
  - Added partition size validation with warning if target is smaller than 1GB.
  - Interactive confirmation before proceeding with small partitions.

- **`/etc/profile`**:
  - Runs `fastfetch` on interactive login if available, falls back to displaying `/etc/issue`.

- **runit stage 1 (`/etc/runit/1`)**:
  - Added kernel module autoloading step (usbhid, ahci, nvme, sd_mod, ext4, vfat).
  - Added udev-less coldplug device detection.
  - Renumbered init stages from 4 to 5 steps.

- **`build/make-rootfs.sh`**:
  - Expanded BINARIES array from ~15 to 70+ essential tools.
  - Added kernel module infrastructure deployment.
  - Added DNS resolver and WiFi configuration directory setup.
  - Added fastfetch config and logo file deployment.
  - Auto-enables network runit service.

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

### Planned for v0.3.0-beta
- Multi-arch automated ARM64 ISO/raw image generation pipeline.
- Hardware cryptographic token support (YubiKey / Nitrokey) integrated directly into `runit` stage 1 disk unlocking.
- Zero-leak RAM wiping daemon utilizing `kexec` and secure memory zeroing before warm reboot.
- Pre-built repository mirrors with BLAKE3 cryptographic ledger.
- Firewall integration (`nftables` / `iptables`) with default paranoid rulesets.
