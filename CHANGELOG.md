# Changelog

All notable changes to **Grintion-OS** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.2] - 2026-11-02

Follow-up fixes for the field report in `ProblemsWhenInstalling.txt`. The
second pass reproduces the login-shell errors and the D-Bus warnings from the
report, keeps the console clean, and makes desktop package installation show
progress instead of appearing to hang.

### Fixed

- **`append_path: command not found` on every login:** a desktop installation pulls in packages whose `/etc/profile.d` snippets (for example `perlbin.sh`) call Arch's `append_path` helper. Grintion's `/etc/profile` never defined it, so a login shell printed one `-bash:` error and one `[CRITICAL]` line per call (ProblemsWhenInstalling.txt #8). `/etc/profile` now provides `append_path` while sourcing `/etc/profile.d`, then unloads it, matching Arch.
- **D-Bus warnings on the installed console:** `dbus-daemon` writes an `Unknown username`/`Unknown group` warning to standard error for every D-Bus policy that names an account created by `systemd-sysusers`, which does not exist here. The `dbus` service now logs to `/var/log/dbus.log`, so the warnings no longer interleave with the login prompt (ProblemsWhenInstalling.txt #7).
- **Missing D-Bus service accounts:** `grintion-desktop install` now creates the users named in `<policy user="...">` (polkitd, colord, avahi, ...) and the groups named in `<policy group="...">` (network) after the packages are installed. Previously those accounts were missing, so the daemons could not drop privileges even when they started.
- **Installer reported a desktop it did not install:** `--desktop` failures only printed a warning, then the closing summary said `desktop: xfce (ready on boot)` and the installer exited 0 (ProblemsWhenInstalling.txt #9). The installer now records the desktop result, reports `NOT installed` with the recovery command, and exits non-zero while still leaving the bootable base system in place.
- **A single slow mirror aborted the whole desktop transaction:** `grintion-desktop` now retries the package transaction once. pacman keeps completed downloads and rolls back a failed transaction, so the retry fetches only the missing packages.
- **The seeded pacman database claimed packages that were not in the image:** `build/seed-pacman-db.py` recorded the command-owning packages and their whole dependency closure, but only the command-owning packages' files were copied. Dependencies such as `glib2` were listed as installed while `libglib-2.0.so.0` was absent, so pacman skipped them and desktop scriptlets failed (`update-desktop-database: error while loading shared libraries`) while pacman still exited 0. Removing `--needed` in 0.8.1 fixed explicitly requested packages only, not their already-seeded dependencies. The seed step now omits any package whose declared shared libraries and binaries are all missing from the rootfs, so pacman installs those libraries as real dependencies.
- **Desktop installation looked hung:** `grintion-desktop` captured the entire `pacman` run in `$(...)` and printed it only at the end. A working 7-10 minute XFCE transaction showed a blank screen, which is why the report described Ctrl+C and a second install attempt (ProblemsWhenInstalling.txt #3, #4 and #9). The package manager output now streams to the console and to `/var/log/grintion-desktop.log`, and the command warns up front that it can take several minutes.

### Tests

- A login-shell test renders `etc/profile` against a temporary `/etc/profile.d` containing a `perlbin.sh` snippet and asserts `append_path` works without errors.
- Tests assert the `dbus` service redirects to `/var/log/dbus.log`, that `grintion-desktop` streams package output and provisions D-Bus accounts, and that the pacman seed drops entries whose libraries and binaries are all missing. The QEMU desktop probe covers the installer's `--desktop` path end to end.

---

## [0.8.1] - 2026-11-01

Fixes for the field report in `ProblemsWhenInstalling.txt`: a live boot with no
network address, `poweroff` hanging until the VM was forced off, and
`grintion-desktop install` reporting success while the display manager never
started.

### Fixed

- **`poweroff`, `reboot` and `halt` hung:** runit stage 3 force-stopped every service in `/var/service`, including the `agetty` that owned the console the command was typed on. `runsv` signals the whole process group, so the getty, the shell and the `poweroff` process died together and the machine stayed up with a dead console. Stage 3 now skips `agetty-*`, and the wrappers run the shutdown sequence in a detached session so a service stop cannot kill it. `-f` now skips the service shutdown instead of being ignored.
- **No network on first boot:** the `network` service scanned `/sys/class/net` and passed kernel pseudo interfaces to `dhcpcd` (`network: starting dhcpcd on eth0 sit0`). `sit0` has no carrier, so `dhcpcd` logged `sit0: unsupported interface type` and the real DHCP exchange on `eth0` was delayed past the first ping. The scan now lives in `network.lib.sh` (`network_wired_interfaces`) and keeps only `ARPHRD_ETHER` links that are not wireless.
- **`sv start display-manager` timing out:** display managers need the D-Bus system bus and the account `dbus-daemon` drops privileges to, neither of which exists without systemd. `grintion-desktop` now installs `dbus`, creates the account named in `system.conf` (`dbus` on current Arch, `messagebus` on older ones), and enables the new `/etc/sv/dbus` service before the display-manager service. The display-manager run script waits for the bus and logs when it is missing instead of exiting silently.
- **Packages that were never really installed:** the image ships a seeded pacman database that lists packages whose files were not copied into the rootfs (`dbus` was "installed" with no `/usr/bin/dbus-daemon`). With `--needed`, pacman skipped them and their dependencies, so package scriptlets failed (`libglib-2.0.so.0` not found) while the install reported success. `grintion-desktop` no longer passes `--needed`, so the requested packages and their dependencies are installed for real.
- **Misleading desktop install result:** `pacman` returns 0 even when package scriptlets fail, so a half-installed desktop still printed "installed successfully". `grintion-desktop` now counts the package manager's `error:` lines and explains them, verifies the display-manager and session binaries exist, and reports whether `display-manager` actually came up (with the tail of `/var/log/display-manager.log` when it did not).

### Changed

- `guide.md` documents the 0.8.0 `grintion-network` commands instead of the hand-written `wpa_passphrase`/`dhcpcd` recipe, and notes that the live shell appears before DHCP finishes.
- `make test-boot` now runs a plain `poweroff` and fails if the VM does not exit, so the shutdown hang cannot regress silently.

### Tests

- Interface filtering, the network service wiring, stage 3 getty handling and `poweroff` argument handling are covered by new tests.

---

## [0.8.0] - 2026-11-01

This release adds the networking, desktop-profile and installer work planned
as F1, F4 and F3 Stage 1.

### Added

- **Network configuration and Wi-Fi (F1):** `/etc/grintion/network.conf`, `network.lib.sh`, `grintion-network` (`status`, `set-static`, `connect`, `disconnect`, `wifi-scan`, `apply`) and an opt-in supervised `wpa_supplicant` service. The `network` service now applies DHCP/static configuration instead of running unfiltered `dhcpcd`.
- **Desktop profiles (F4):** `/etc/grintion/desktops.d/*.conf`, `grintion-desktop uninstall`, `list --json`, and `/etc/grintion/drivers.conf` for the GPU matrix.
- **Installer Stage 1 (F3):** `--swap-size MIB` creates a swap partition, and partition names come from `lsblk` after `partprobe` instead of a device-name suffix guess.
- **Regression tests:** network configuration, desktop profiles and installer argument handling.

### Security

- Wi-Fi credentials are written with mode `0600` to both `network.conf` and the generated `wpa_supplicant.conf`.

### Release

- The 0.8.0 ISO (127 MiB, SHA-256 `0d86610c97a73f20b297cf4049ffcbc392a879a5a3846cd5d92fa880ca429158`) passed the BIOS and UEFI live boot tests and the BIOS and UEFI install tests. It is published as a GitHub Release asset because it exceeds the 100 MB git-file limit.

LUKS full-disk encryption, custom partitioning, Secure Boot and ARM64 remain
roadmap items; they were not started.

---

## [0.7.0] - 2026-11-01

This release is a correctness pass over 0.6.1: every item in the handoff bug
report is addressed, and `garb` gains the missing lifecycle commands and safety
checks.

### Added

- **`garb clean`, `garb list`, `garb info --installed`, `garb verify --format json`:** cache purge, installed/upgradable listings, installed-only metadata and machine-readable integrity reports.
- **Package conflict detection:** installing a file already owned by another package is refused unless `--force` is used.
- **Local archive dependency resolution:** `garb install ./pkg.garb` now resolves and installs the archive's `[dependencies] runtime` entries from the loaded indexes, and fails fast when one is unavailable.
- **Full timezone database:** the live image ships `/usr/share/zoneinfo`, so the documented `ln -sf /usr/share/zoneinfo/Region/City /etc/localtime` step works.
- **UEFI installer test target:** `make test-install-uefi` runs the end-to-end install on OVMF.
- **Regression tests:** shutdown parsing, `limine-deploy`, reverse dependencies, local dependencies, conflicts, JSON verification, cache cleaning, malformed Garbfiles and symlinks to directories.

### Fixed

- **`limine-deploy`:** installs the kernel and initramfs referenced by `limine.conf` into `EFI/grintion/` (or aborts) instead of producing an unbootable ESP. New `--kernel`, `--initramfs` and `--asset-dir` options.
- **`shutdown`:** real option parsing (`-r`, `-h`, `-P`, `-H`, `-c`, `now`, `+MINUTES`, `HH:MM`); `-c` cancels instead of powering off, and `-h +5` schedules instead of acting immediately.
- **Power wrappers:** `poweroff`, `reboot` and `halt` run runit stage 3 first, so services stop cleanly and the random seed is saved.
- **`garb remove`:** refuses to remove a package that another installed package depends on unless `--force` is given.
- **`garb` rollback:** replaces a directory destination safely and keeps the backup directory when any restore step fails, instead of losing the originals.
- **`garb build`:** packages symlinks that point at directories instead of silently dropping them.
- **`garb` errors:** malformed TOML and bad integers print a `[-]` message rather than a Python traceback; unsigned repositories work with `--allow-unsigned` even when no `index.json.sig` exists.
- **Live root account:** `/etc/shadow` now ships `root:*:...` (locked) instead of an empty password field; console access still uses the `live-shell` bypass.
- **`display-manager` service:** `exec`s the daemon so runit supervises a live process, and `grintion-desktop` records the chosen DM in `/etc/grintion/display-manager` instead of regenerating a drifting run script.
- **`network` service:** starts `dhcpcd` only on wired interfaces, matching the documentation and avoiding wireless carrier timeouts.
- **`grintion-persist`:** requires root up front instead of failing halfway through formatting.
- **`grintion-desktop`:** fixed status reporting and no longer writes a bogus `exec sway` into `.xinitrc` (Sway is Wayland-only).
- **Early boot:** `live-init` and `install-init` share one `recovery.sh`, so the rescue shell is maintained in one place.
- **Version metadata:** `VERSION`, `/etc/grintion/version`, the `garb` version, README and current-facing docs all report 0.7.0.

### Security

- The live image no longer exposes a PAM account with a blank password. `su` and `login` require a real secret; the ephemeral console session is provided by `agetty --skip-login` + `live-shell`.

---

## [0.6.1] - 2026-10-31

### Fixed

- **System Power Wrappers (`poweroff`, `reboot`, `shutdown`, `halt`):** Deployed native busybox-backed power wrapper scripts to `/usr/bin/` and `/usr/sbin/`, completely preventing `System has not been booted with systemd as init system (PID 1)` errors and allowing clean, direct system restart and shutdown without requiring the `-f` flag.
- **Display Manager Logging & Crash Isolation:** Redirected display manager execution logs to `/var/log/display-manager.log` and added a 3-second restart cooldown, preventing runaway crash loops and terminal output interleaving on `tty1`.
- **LightDM System User & Greeter Auto-Configuration:** Automatically provisions the `lightdm` system user and group, creates required state/log directories (`/var/lib/lightdm`, `/var/log/lightdm`), and configures `greeter-session=lightdm-gtk-greeter` in `/etc/lightdm/lightdm.conf` during desktop installation and in the base rootfs.
- **X11 Magic Cookie Generator (`mcookie` & `util-linux`):** Added `mcookie` directly into `config/rootfs.required-binaries` and `util-linux` to desktop dependencies with an automatic `openssl` fallback generator in `/usr/bin/mcookie`, ensuring `startx` initializes Xauth security cookies and boots directly without manual intervention.
- **Automated Desktop Session Initialization (`.xinitrc`):** Enhanced `grintion-desktop` to automatically propagate the desktop session command (`exec startxfce4`, etc.) across `/etc/skel/.xinitrc`, `/root/.xinitrc`, and all existing user home directories with proper file ownership.
- **Installer Chrooted Environment:** Upgraded `grintion-install` to mount `/proc`, `/sys`, `/dev`, and `/run` with working DNS resolution before running desktop pre-installation, guaranteeing package installation and user account creation succeed on target disks.
- **Runit Service Path Compatibility (`SVDIR` and `/service`):** Exported `SVDIR=/var/service` in `/etc/profile` and established `/service -> /var/service` symlink in rootfs so `sv start <service>` and `sv status <service>` commands work reliably without requiring manual `/var/service/` path prefixes.

---

## [0.6.0] - 2026-10-31

### Added

- **Authentic Grintion-OS Visual Branding:** Deployed the official Unicode block logo across `/etc/grintion-logo.txt` (used by `fastfetch`), `/etc/issue.in` (live boot banner), `/etc/issue.installed.in` (installed boot banner), and `bin/grintion-persist`.
- **Desktop Environment Management (`grintion-desktop`):** Full interactive and scripted suite supporting **XFCE**, **GNOME**, **KDE Plasma**, **LXQt**, **Sway**, and **i3** with numeric (`1`–`6`) and name-based selection.
- **Automated Repository Synchronization:** Enhanced `grintion-desktop` to automatically synchronize package databases (`pacman -Sy`) before package installation, preventing missing database errors on freshly booted systems.

### Fixed

- **Clean Console Login Experience:** Isolated network service (`dhcpcd`) logging in `etc/sv/network/run` to `/var/log/dhcpcd.log`, eliminating terminal prompt interleaving and avoiding displaced login prompts on `tty1`.
- **Package Conflict Resolution (`--overwrite '*'`):** Passed `--overwrite '*'` to `pacman` during package installation and upgrades in `garb` and `grintion-desktop`, safely handling pre-bundled shared libraries without transaction commit failures.
- **Primary Console Routing:** Swapped kernel boot console order to `console=ttyS0,115200 console=tty0` so `tty0` (display screen and keyboard) is the primary interactive console.
- **Panic-Proof Early Boot:** Hardened `init/live-init` and `init/install-init` with error traps and persistent shell restart loops to prevent PID 1 kernel panics.

---

## [0.5.4] - 2026-10-26

### Fixed

- **Authentic Grintion-OS Logo:** Replaced placeholder banner across `/etc/grintion-logo.txt`, `/etc/issue.in`, `/etc/issue.installed.in`, and `bin/grintion-persist` with the authentic Grintion-OS block emblem.
- **Console Login Output Cleanliness:** Redirected background `dhcpcd` logs in `etc/sv/network/run` to `/var/log/dhcpcd.log` so network carrier/lease negotiation messages no longer spill over the active login prompt on `tty1`.

---

## [0.5.3] - 2026-10-24

### Fixed

- **Pacman File Conflict Resolution (`--overwrite '*'`):** Configured `garb` and `grintion-desktop` to pass `--overwrite '*'` to pacman during package installations and upgrades. This eliminates `error: failed to commit transaction (conflicting files)` when installing packages (such as Xorg, X11 libraries, FreeType, Fontconfig) whose shared libraries were pre-bundled into `/usr/lib/` during base image creation.
- **Unit Test Updates:** Updated `tests/test_garb.py` (`test_pacman_backend_translation`) to verify `--overwrite '*'` argument passing.

---

## [0.5.2] - 2026-10-23

### Fixed

- **Desktop Installer (`grintion-desktop`) Package Resolution:** Fixed standard output leakage in `detect_gpu_drivers` where informational log messages (e.g. `[*] Generic / VESA display detected`) were captured into package arrays, causing pacman transaction failures (`target not found: [*]`, `Generic`, `/`, `VESA`, `display`, `detected`). Information logs are now cleanly directed to `stderr`.
- **Interactive Desktop Menu Selection:** Added support for numeric choices (`1` for XFCE, `2` for GNOME, `3` for KDE Plasma, `4` for LXQt, `5` for Sway, `6` for i3) in addition to environment names.
- **VM Network Documentation:** Added documentation in `README.md` and `docs/INSTALL.md` noting the `Intel PRO/1000 MT Desktop (82540EM)` adapter type recommendation in VirtualBox for instant automatic network configuration.

---

## [0.5.1] - 2026-10-21

### Fixed

- **Primary Console Routing (`console=tty0`):** Swapped console ordering in `build/build-iso.sh`, `bin/grintion-install`, and `bin/limine-deploy` from `console=tty0 console=ttyS0,115200` to `console=ttyS0,115200 console=tty0`. In Linux, the last `console=` parameter becomes `/dev/console` (primary standard input/output). Placing `tty0` last ensures that the display screen and keyboard are the primary interactive console on VirtualBox, VMware, and physical hardware, while still mirroring kernel log messages over serial (`ttyS0`).
- **Emergency Rescue & Kernel Panic Prevention:** Hardened `init/live-init` and `init/install-init` with an interactive shell loop and an early exit trap (`trap 'rescue ...' EXIT ERR`). If an error or out-of-memory condition occurs during early boot, PID 1 no longer exits with `exitcode=0x00000100` (`Kernel panic: Attempted to kill init!`), but instead stays active and presents an interactive emergency shell on the screen.
- **Virtual Machine Hardware Guidelines:** Added VM memory and hardware configuration guidelines to `docs/INSTALL.md` noting the minimum 2048 MB RAM requirement for live overlay decompression.

---

## [0.5.0] - 2026-10-4

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

## [0.4.0] - 2026-9-28

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

## [0.3.0-alpha] - 2026-9-19

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

## [0.2.0-alpha] - 2026-9-11

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

## [0.1.0-alpha] - 2026-9-10

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
