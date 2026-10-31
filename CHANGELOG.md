# Changelog

All notable changes to **Grintion-OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.2] - 2026-10-31

### Fixed

- **Desktop Installer (`grintion-desktop`) Package Resolution:** Fixed standard output leakage in `detect_gpu_drivers` where informational log messages (e.g. `[*] Generic / VESA display detected`) were captured into package arrays, causing pacman transaction failures (`target not found: [*]`, `Generic`, `/`, `VESA`, `display`, `detected`). Information logs are now cleanly directed to `stderr`.
- **Interactive Desktop Menu Selection:** Added support for numeric choices (`1` for XFCE, `2` for GNOME, `3` for KDE Plasma, `4` for LXQt, `5` for Sway, `6` for i3) in addition to environment names.
- **VM Network Documentation:** Added documentation in `README.md` and `docs/INSTALL.md` noting the `Intel PRO/1000 MT Desktop (82540EM)` adapter type recommendation in VirtualBox for instant automatic network configuration.

---

## [0.5.1] - 2026-10-31

### Fixed

- **Primary Console Routing (`console=tty0`):** Swapped console ordering in `build/build-iso.sh`, `bin/grintion-install`, and `bin/limine-deploy` from `console=tty0 console=ttyS0,115200` to `console=ttyS0,115200 console=tty0`. In Linux, the last `console=` parameter becomes `/dev/console` (primary standard input/output). Placing `tty0` last ensures that the display screen and keyboard are the primary interactive console on VirtualBox, VMware, and physical hardware, while still mirroring kernel log messages over serial (`ttyS0`).
- **Emergency Rescue & Kernel Panic Prevention:** Hardened `init/live-init` and `init/install-init` with an interactive shell loop and an early exit trap (`trap 'rescue ...' EXIT ERR`). If an error or out-of-memory condition occurs during early boot, PID 1 no longer exits with `exitcode=0x00000100` (`Kernel panic: Attempted to kill init!`), but instead stays active and presents an interactive emergency shell on the screen.
- **Virtual Machine Hardware Guidelines:** Added VM memory and hardware configuration guidelines to `docs/INSTALL.md` noting the minimum 2048 MB RAM requirement for live overlay decompression.

---

## [0.5.0] - 2026-10-31

### Added

- **Desktop & GUI Support:**
  - New `grintion-desktop` utility for managing, installing, and configuring graphical desktop environments and window managers: **XFCE**, **GNOME**, **KDE Plasma**, **LXQt**, **Sway**, and **i3**.
  - Hardware graphics driver auto-detection (`grintion-desktop drivers`) supporting Intel, AMD/Radeon, NVIDIA, QEMU/KVM VirtIO, VMware, and VirtualBox.
  - Installer integration: `grintion-install --desktop <env>` supports pre-installing a desktop environment directly onto the target disk.
  - Runit `display-manager` service template in `/etc/sv/display-manager` to supervise LightDM, SDDM, or GDM.
  - Comprehensive documentation in `docs/DESKTOP-GUI.md`.
- **Package Manager & Pacman Backend:**
  - The live image bundles **pacman** with `/etc/pacman.conf`, official Arch Linux repositories (`core`, `extra`), the Arch public keyring, and gpg helpers.
  - `build/seed-pacman-db.py` seeds `/var/lib/pacman/local` with packages shipped in the image and their dependency closures.
  - `garb` delegates `install`, `remove`, `update`, `search`, `info`, `verify`, and `upgrade` to `pacman` (with `--noconfirm` for non-interactive commands).
- **Network & Diagnostics:**
  - `etc/resolv.conf.head` supplies fallback public resolvers (`1.1.1.1`, `8.8.8.8`) prepended by `dhcpcd` to prevent early-boot DNS resolution race conditions.
  - `grintion-doctor` reports missing runtime binaries, sudo policy plugin availability, and version contract integrity.
  - Interactive bash provides helpful hints when attempting to launch desktops (`startx`, `sway`, etc.) or unknown commands.

### Fixed

- **Filesystem Mounts (`/etc/mtab`):** Added symlink `/etc/mtab -> /proc/self/mounts` in `build/make-rootfs.sh`. This resolves pacman's `could not determine filesystem mount points` and `CheckSpace` transaction commit failures on overlay roots.
- **Sudoers Plugin:** Shipped `/usr/lib/sudo/sudoers.so` so `sudo` can load its policy plugin without failing before PAM authentication.
- **Python Compatibility:** Fixed `re.split` maxsplit keyword usage in `build/seed-pacman-db.py` to prevent Python 3.13+ deprecation warnings.

### Verified

- Verified end-to-end pacman transactions in QEMU:
  - `garb update` cleanly downloads and verifies Arch official databases.
  - `garb install jq` installs `oniguruma` and `jq 1.8.2-1`.
  - `jq --version` runs correctly.
  - `garb remove jq` cleanly removes installed packages.


---

## [0.4.0] - 2026-10-30

The first supported release: a console-only x86_64 system that boots from a
hybrid BIOS/UEFI ISO, runs from an overlay, installs to a disk, and uses a
package manager with signed repository indexes.

### Added

- **Kernel:** Linux 6.12.114 built from kernel.org source with localversion
  `-grintion` and `config/kernel-hardened.config`; the required-symbol contract
  is enforced by `build/check-kernel-config.sh`.
- **Boot:** hybrid ISO9660 image with Limine 8.7.0 for BIOS and UEFI, plus a
  recovery-shell entry that starts `/bin/sh` without runit.
- **Live system:** the complete root is a read-only initramfs lower layer with a
  tmpfs overlay upper layer; `grintion-persist` can place the upper layer on an
  ext4 partition labelled `GRINTION_PERSIST` so changes survive reboot.
- **Installer:** `grintion-install` repartitions a whole disk with GPT, creates
  a 512 MiB FAT32 ESP and an ext4 root, copies the live system, creates one
  `wheel` user, writes `/etc/fstab` by UUID, and installs Limine. Interactive,
  unattended and `--dry-run` modes are supported.
- **Init:** runit with `runsvdir` supervision; services for two local gettys, a
  serial getty, DHCP, the nftables firewall, syslog and a local hook.
- **Package manager:** `garb` 1.0 with Ed25519-signed indexes, per-file
  SHA-256 verification, runtime dependencies, safe extraction, transactional
  install/rollback, upgrade, removal and integrity verification.
- **Hardening:** BPF syscall, kexec, hibernation and `/dev/mem` disabled at
  build time; io_uring disabled and Yama ptrace scope 2 at runtime; restricted
  `dmesg` and kernel pointers; protected links, FIFOs and regular files; core
  dumps disabled; default-drop nftables input policy; PAM faillock
  configuration.
- **Documentation:** installation, build, architecture, package-manager,
  verification, roadmap, third-party and security documents for the 1.0.0
  release.
- **Tests:** static checks (`make check`), `garb` unit/integration tests, live
  BIOS/UEFI boot tests, and an end-to-end installer test that reinstalls,
  reboots from disk, logs in and verifies networking.

### Changed

- The live userland is assembled from an explicit required-command list; a
  missing command fails the build instead of producing a partial image.
- PAM uses a single working `system-auth` stack; password changes and `sudo`
  work on installed systems.
- The installer writes account databases directly instead of relying on
  `useradd` inside a minimal chroot.
- Kernel, live initramfs and installed initramfs are built as separate,
  reproducible-metadata artifacts; `BUILD-INFO` records their hashes.
- Documentation now states the project's real boundaries: the userland is
  curated from the build host, not bootstrapped from source.

### Removed

- Legacy `src/garb`, `dist/` packages, `rootfs_overlay/` and the old
  `packages/*/Garbfile` manifests for unshipped GUI components.
- The `autotest` service is no longer shipped in the live image. The installer
  test drives `grintion-install` explicitly over the serial console.
- The unenabled `wpa_supplicant` runit service. Wi-Fi remains a manual setup
  documented in [docs/INSTALL.md](docs/INSTALL.md).

### Security

- The installed system locks root by default; administrative work goes through
  the created `wheel` user and `sudo`.
- The live image intentionally provides passwordless root on the console. It is
  an ephemeral installation medium, not a hardened workstation image.
- No Secure Boot, verified boot, disk encryption, mandatory access control or
  independent security audit is included. See [SECURITY.md](SECURITY.md).

### Known limitations

- No hosted package repository and no signed release artifacts.
- No installer support for encryption, LVM, dual boot or custom partitioning.
- No ARM64 build, graphical desktop, Wi-Fi roaming service or automatic
  updates.
- The userland version is whatever the Arch build host provides; builds are not
  bit-for-bit reproducible across hosts.

---

## Historical development snapshots

These entries are preserved from the alpha period. They are historical records,
not a description of 1.0.0: several items (multi-architecture images, Flatpak /
Snap / AppImage sandboxing, GUI packages, BLAKE3 ledgers) were planned or
prototyped but were **not shipped**. Use the 1.0.0 sections above and the
current documentation as the source of truth.

---

## [0.3.0-alpha] - 2026-10-28

### Fixed

- Expanded the live rootfs from about 70 to 120+ commands, including `clear`,
  `reset`, `tput`, `ssh`, `scp`, `sftp`, `ssh-keygen`, `ssh-agent`, `whoami`,
  `groups`, `pgrep`, `pkill`, `watch`, `nc`, `ifconfig`, `route`,
  `wpa_passphrase`, `vim`, `zip`, `fsck`, `mkswap`, `lscpu`, `fuser`, `lsof`,
  `hexdump`, `stty`, `expr`, `seq`, `nice`, `nohup`, `flock` and `timeout`.
- The build now reports missing binaries instead of silently skipping them.
- Deployed the terminfo database so `clear`, `reset`, `tput`, `nano`, `vi` and
  other terminal-aware programs work.
- Added `/etc/sudoers` with `wheel` support and secure defaults.
- Added `/etc/ssh/ssh_config` for the OpenSSH client.
- Added `/etc/nsswitch.conf` for user, group and DNS lookups.
- Added `/etc/os-release`, `/etc/shells` and a generated machine ID.

---

## [0.2.0-alpha] - 2026-10-28

### Added

- **Networking:** `dhcpcd` with a runit service, `wpa_supplicant`, `wpa_cli` and
  `iw` for manual Wi-Fi setup, plus `curl`, `wget`, `ping`, `ss`, `dig`,
  `nslookup` and `rfkill` in the live image.
- **Commands:** process, user, editor, module, hardware, text-processing,
  archive and power-management utilities.
- **Drivers:** kernel modules deployed into the image and loaded at boot, with
  udev-less coldplug through sysfs uevents.
- **Fastfetch:** login banner configuration and a Grintion-OS ASCII logo.
- **Installer:** copies the kernel and installed initramfs to the target and
  writes the ESP entry to `/etc/fstab`.
- **Persistence:** `grintion-persist` warns before using a small partition.
- **GUI manifests (not shipped in 1.0.0):** Garbfiles for Xorg, Wayland, i3,
  sway, openbox, Xfce, Plasma, SDDM, Mesa, ALSA and linux-firmware.

---

## [0.1.0-alpha] - 2026-10-26

### Added

- Initial independent OS specification on a vanilla Linux kernel and the MISS
  philosophy: Minimalist, Independent, Secure, Stable.
- `garb` package manager with install, remove, update, search, verify and a
  declarative `Garbfile` format. The sandbox and multi-format package support
  described in the original notes was planned, not shipped.
- runit three-stage init: `/etc/runit/1` mounts and sysctls, `/etc/runit/2`
  supervises `/var/service`, `/etc/runit/3` stops services and syncs.
- Live RAM environment with gettys, syslog, a network service and the
  `grintion-install` / `grintion-persist` tools.
- Hybrid BIOS/UEFI ISO build with Limine and xorriso.
- Initial README, SECURITY, CONTRIBUTING and LICENSE documents.
