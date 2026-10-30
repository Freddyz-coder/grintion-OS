# Changelog

All notable changes to **Grintion-OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- `garb` can delegate `install`, `remove`, `update`, `search`, `info`, `verify`
  and `upgrade` to an installed `pacman` or `apk`. Auto-detection is limited to
  the running system; `--backend native` forces the signed-repository backend.
- `grintion-doctor` checks required commands, the sudo policy plugin and the
  running version, and reports missing components as critical failures.
- Interactive bash now reports unknown commands as `[CRITICAL]` and explains
  the common `pacman`, `apk`, `man` and `clean` cases.

### Fixed

- `sudo` now ships `/usr/lib/sudo/sudoers.so`; the binary alone could not load
  its policy plugin and failed before authentication.

---

## [1.0.0] - 2026-10-31

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

## [0.2.1-alpha] - 2026-10-30

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

## [0.2.0-alpha] - 2026-10-30

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

## [0.1.0-alpha] - 2026-10-28

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
