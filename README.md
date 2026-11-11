# Grintion-OS

A small, source-built Linux operating system for x86_64. It boots from a
read-only squash-free initramfs, runs from an overlay in RAM, installs to a
disk with one command, and ships a package manager with signed repository
indexes.

**Minimal - Independent - Secure - Stable** (MISS)

- **Version:** 0.12.0
- **Architecture:** x86_64
- **Boot:** BIOS and UEFI (Limine 8.7.0)
- **Kernel:** Linux 6.12.114 built from kernel.org source with a hardening
  configuration fragment
- **Init:** runit
- **Userland:** GNU coreutils, glibc, bash, util-linux, PAM, OpenSSH client
- **GUI & Desktop:** Streamlined console prompt for pre-installation, maintenance, and setup. Desktop packages and GPU drivers install with `grintion-desktop` or `garb`. XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway are verified in QEMU/KVM; GNOME is refused because `gnome-session` 51 requires the systemd user session manager
- **Audio:** HDA and USB audio are built into the kernel; desktop profiles install PipeWire, WirePlumber, firmware and the PulseAudio compatibility daemon. A shared session helper starts the stack and unmutes every detected ALSA card; it is used by the X11 hook and by XDG autostart for Wayland desktops. Playback is verified end-to-end on XFCE with QEMU audio capture

0.12.0 is a security release: AppArmor is compiled into the kernel and loaded
at boot, and X11 no longer listens on TCP or abstract sockets. See
[docs/SECURITY-HARDENING.md](docs/SECURITY-HARDENING.md).

Grintion-OS 0.12.0 is built from this tree. There is no hosted binary
repository; build the ISO, or install the prerequisites and run `make`. Official
release artifacts can be signed with `make sign-release` and verified with
`bin/grintion-release-verify` (see [docs/REPO-KEY-CEREMONY.md](docs/REPO-KEY-CEREMONY.md)).

---

## What the system does

| Area | Behaviour |
| --- | --- |
| Live boot | Kernel and initramfs load entirely into RAM. The root is a tmpfs overlay, so the live session can write anywhere without touching a disk. |
| Installed boot | The installer copies the live root to an ext4 root partition and installs Limine for BIOS or UEFI. Root is read-write. |
| Networking | `/etc/grintion/network.conf` drives DHCP or static addressing; `grintion-network` configures static IPs and supervised Wi-Fi (`wpa_supplicant`). DNS fallback resolvers keep name resolution responsive from early boot. |
| Desktop & GUI | Boots to a clean prompt for pre-installation and configuration. Graphical desktop environments and GPU drivers can be pre-installed with `grintion-install --desktop` or installed on-demand with `grintion-desktop`. XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway were rendered in QEMU/KVM; GNOME is refused because `gnome-session` 51 requires systemd. |
| Audio | HDA and USB audio are built into the kernel. Desktop profiles install PipeWire, WirePlumber, firmware and ALSA tools. The shared `grintion-audio` helper is started by the X11 hook or XDG autostart, and unmutes every detected ALSA card; WirePlumber enumerates real sinks through udev instead of a hard-coded `plughw:0,0`. PipeWire playback was captured on the XFCE QEMU probe. Direct ALSA is only usable after PipeWire releases the PCM. |
| Services | runit supervises two local gettys, a serial getty, networking, the nftables firewall, syslogd, optional display manager, and a local hook. |
| Accounts | root logs in on the live image. The installer creates one administrative user in `wheel`; root stays locked unless `--root-password-stdin` is used. |
| Packages | `garb` installs, removes, upgrades and verifies packages via native Ed25519-signed repositories or delegating to the bundled `pacman` backend for Arch official packages. |
| Persistence | `grintion-persist` formats a partition labelled `GRINTION_PERSIST`; the live init mounts it as the overlay upper layer, so changes survive reboot. |
| Hardening | Kernel configuration fragment, restricted `/proc` and `dmesg`, ASLR, Yama ptrace, AppArmor mandatory access control compiled into the kernel and loaded by the `apparmor` service at boot, Bubblewrap application sandboxing, USBGuard data-blocking, auditd logging with sudo I/O trails, file integrity verification (`grintion-integrity`), and customizable security profiles (`workstation`, `server`, `kiosk`, `air-gapped`). X11 starts without TCP or abstract-socket listeners and requires a per-session cookie; `grintion-security-report` flags an exposed X server. |
| Configuration | Single unified system tool (`grintion-config`) for timezones, locales, keymaps, hostnames, user accounts, power governors, and background services. |
| Resilience | Watchdog service supervision with crash backoff, atomic package generations and rollback (`garb generations`), Btrfs snapshots, and automated self-healing (`grintion-doctor --fix`). |

Documentation:
- [Handbook](docs/HANDBOOK.md) (Full 10-chapter manual)
- [Guía Rápida en Español](docs/HANDBOOK-ES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Installation](docs/INSTALL.md)
- [Security Hardening](docs/SECURITY-HARDENING.md)
- [Hardware & Lab Validation](docs/HARDWARE-LAB.md)
- [Package Ecosystem](docs/PACKAGE-ECOSYSTEM.md)
- [Performance Baselines](docs/PERFORMANCE-BASELINES.md)
- [Tracked Binary Provenance](docs/BINARY-PROVENANCE.md)
- [Roadmap](docs/ROADMAP.md)

---

## Install

Boot the ISO, then:

```sh
grintion-install --disk /dev/vda
```

The installer asks for confirmation, repartitions the **whole disk**, creates a
512 MiB EFI system partition plus an ext4 root, copies the live root, installs
Limine, and writes `/etc/fstab`. Existing data on the disk is destroyed.

Unattended example:

```sh
printf '%s\n' 'change-me' | grintion-install --unattended --disk /dev/vda \
    --hostname box --user grintion --password-stdin
```

Add `--dry-run` to print the plan without touching the disk, or
`--swap-size MIB` to add a swap partition. See
[docs/INSTALL.md](docs/INSTALL.md) for persistence, post-install steps and
troubleshooting.

---

## Package manager

Repositories are directories containing `.garb` packages, an `index.json` and a
detached Ed25519 signature. The client trusts only keys in
`/etc/garb/keys/*.pub` and checks the signature before reading any index entry.

The image ships **pacman** as an external backend; `apk` is supported by the
translator but is not installed. `garb` uses pacman for `install`, `remove`,
`update`, `search`, `info`, `verify` and `upgrade`. Auto-detection only applies
to the running system (`--root /`); use `--backend pacman|apk|native` to choose
explicitly. Delegation bypasses garb's signature and transaction checks.

**Backend integration:** `garb` supports dual backends:
- **Pacman backend (bundled):** Delegates directly to Arch Linux official repositories (`core`, `extra`) using the bundled `pacman` and Arch public keyrings.
- **Native backend:** Uses Ed25519-signed repository indexes and SHA-256 archive verification for custom packages.

```sh
garb update                      # Synchronize official repository databases
garb search jq                   # Search packages
garb info jq                     # Package metadata
garb install jq                  # Install package and dependencies
garb verify                      # Verify file integrity
garb list                        # List native-backend packages
garb list --upgradable           # Native-backend upgrades
garb clean                       # Purge the native repository cache
garb remove jq                   # Remove package
```

Build the demo repository from this tree:

```sh
make packages          # output/packages + unsigned index
```

Signing, the on-disk format, the threat model and delegation details are in
[docs/PACKAGE-MANAGER.md](docs/PACKAGE-MANAGER.md).

---

## Desktop & GUI Support

Grintion-OS boots into a clean, minimal console prompt designed for pre-installation, partitioning, and system administration. Desktop environments and GPU drivers can be installed and configured:

> **Verification status:** XFCE and i3 (LightDM + Xorg) were rendered in
> QEMU/KVM with working keyboard and pointer input, and a 440 Hz tone played
> through PipeWire was captured from the emulated HDA device. KDE Plasma was
> rendered on Wayland through SDDM, LXQt through LightDM, and Sway directly on
> Wayland with `swaybg` and `swaybar`. GNOME is not supported: its session
> manager requires systemd. See [docs/VERIFICATION.md](docs/VERIFICATION.md).

### Pre-installing with the installer

```sh
# Pre-install a desktop environment during disk installation
grintion-install --disk /dev/vda --user myuser --desktop xfce
```

### Installing via `grintion-desktop`

Use `grintion-desktop` on the live overlay or an installed system to install environments and auto-detect hardware graphics drivers:

```sh
grintion-desktop list               # View supported desktop environments
grintion-desktop install xfce       # Fast & lightweight traditional desktop (Recommended)
grintion-desktop install kde        # KDE Plasma - verified Wayland session
grintion-desktop install lxqt       # Ultra-lightweight Qt desktop (verified)
grintion-desktop install sway       # Wayland tiling compositor (verified)
grintion-desktop drivers            # Auto-detect GPU and install graphics drivers
```

LightDM and SDDM are supervised by runit (`/var/service/display-manager`); GDM is not used because it requires systemd-logind. See [docs/DESKTOP-GUI.md](docs/DESKTOP-GUI.md) for full instructions.

---

## Tests

```sh
make check       # shellcheck, tracked-binary hashes, syntax, Python tests
make rootfs-pinned # build the rootfs from the dated Arch Linux Archive snapshot
make test-garb   # signed repository and transaction tests
make test-boot   # boot the ISO under BIOS and UEFI in QEMU
make test-network # boot five virtual NIC models under BIOS/QEMU
make test-install # install to a disk, reboot, log in, check networking
make test-install-uefi # install under UEFI/OVMF and reboot from it
make test-all    # all of the above
```

The static gate runs in an Arch container in CI with shellcheck and pytest, and
writes `output/junit.xml`. The runtime tests need KVM and OVMF (`edk2-ovmf`) and
run on a self-hosted KVM runner; GitHub-hosted runners do not silently skip them.
Exact coverage and the results recorded for this release are in
[docs/VERIFICATION.md](docs/VERIFICATION.md).

---

## What "independent" means

Grintion-OS is independent in **integration**, not in the sense of writing every
component from scratch:

- The kernel, bootloader, init, C library and base utilities are upstream
  projects, used unmodified except for configuration. Tracked binaries are
  listed with their provenance in [docs/BINARY-PROVENANCE.md](docs/BINARY-PROVENANCE.md)
  and pinned by SHA-256 in `config/binaries.sha256`.
- The live userland is **not** built from source by this repository. It is a
  curated set of distribution packages, with every required command listed in
  `config/rootfs.required-binaries` and every shared library resolved
  explicitly. `make rootfs-pinned` takes those packages from the dated Arch
  Linux Archive snapshot in `config/arch-snapshot`; plain `make rootfs` still
  uses the build host for fast local iteration.
- `garb` packages are prebuilt file trees. There is no source build recipe, no
  compiler toolchain in the image, and no cross-compilation.
- The optional `pacman` backend installs Arch packages from official
  repositories. It is an explicit Arch dependency, not independent packaging.

This is a deliberate trade-off: a small, auditable image now, with a documented
path to a from-source bootstrap later. Do not describe the image as
"from-scratch" or "built entirely from source"; it is not.

---

## Support matrix

| Feature | 0.12.0 |
| --- | --- |
| x86_64 BIOS boot | Yes, tested in QEMU. Bare-metal lab logs are not published; see [docs/VERIFICATION.md](docs/VERIFICATION.md). |
| x86_64 UEFI boot | Yes, tested in QEMU with OVMF. Bare-metal lab logs are not published; see [docs/VERIFICATION.md](docs/VERIFICATION.md). |
| Secure Boot | Supported via local MOK keys (`grintion-secureboot`) & UKI (`grintion-uki`); pre-enrolled Microsoft 3rd-party CA shim is not bundled (see [docs/SECURE-BOOT.md](docs/SECURE-BOOT.md)) |
| ARM64 | Build scripts are x86_64-only |
| Graphical desktop | XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway are verified in QEMU/KVM. GNOME is not supported because `gnome-session` 51 requires `org.freedesktop.systemd1` |
| Audio | PipeWire playback verified end-to-end on XFCE (QEMU WAV capture) with a dynamically enumerated sink; all ALSA cards are unmuted. Direct ALSA playback requires suspending PipeWire first. PipeWire 1.6.11 is the current Arch stable version and includes the upstream `pipewire-alsa` drain fix |
| Wi-Fi | Supported via `grintion-network` (Enterprise WPA2/WPA3, priority roaming, reconnection, MAC randomization, DNS leak test) |
| Disk encryption | Supported; LUKS2 root (`--encrypt`), encrypted swap (`/etc/sv/cryptswap`), and encrypted `/home` (`--encrypt-home`) via `grintion-install` |
| Snapshots / rollback | Supported; Btrfs root snapshots and rollback (`grintion-snapshot`), boot failure auto-rollback (`grintion-boot-health`), and package generations (`garb generations` / `rollback-generation`) |
| Package installation | Supported; dual backends (`garb` native signed repo & bundled `pacman` with Arch official repos) |
| Hosted binary repository | **No repository is hosted.** Release channels, delta updates and signed index metadata exist as tooling; the README does not claim a public server. |
| Signed release artifacts | Tooling and a tag-triggered release workflow exist; no signed release has been published yet. `build/sign-release.sh` signs `SHA256SUMS` and `BUILD-INFO`, verified via `grintion-release-verify` (see [docs/REPO-KEY-CEREMONY.md](docs/REPO-KEY-CEREMONY.md)) |

Unsupported configurations are not "known broken"; they are simply outside what
this release builds and tests.

---

## Repository layout

```text
bin/            grintion-install, grintion-config, grintion-desktop, grintion-persist, grintion-chroot,
                garb, limine-deploy, grintion-doctor, grintion-security-report, grintion-hwinfo,
                grintion-release-verify, grintion-secureboot, grintion-uki, grintion-attest,
                grintion-tpm-luks, grintion-snapshot, grintion-boot-health, grintion-backup,
                grintion-reset, grintion-network, grintion-session, grintion-audit,
                grintion-integrity, grintion-audit-log, grintion-sandbox, grintion-shield,
                grintion-vault, grintion-usb, grintion-watchdog, grintion-tour, grintion-help, grintion-report
build/          kernel, rootfs, initramfs, ISO build scripts, and test/validation suites
config/         kernel fragment, required binaries, PAM modules, setuid list
etc/            live and installed system configuration, runit services, profiles
init/           live-init (PID 1) and install-init (installed initramfs PID 1)
packages/       demo Garbfile packages used by the repository tests
tests/          unit, integration, and QEMU end-to-end test suites
tools/          pinned build tools and sources (busybox, runit, dhcpcd, limine)
docs/           comprehensive user handbook, architecture, security hardening, recovery, and lab docs
```

---

## Security

Read [SECURITY.md](SECURITY.md) before relying on this system for anything
sensitive. The short version: the design is defensive and implements LUKS2
encryption, AppArmor MAC, user-controlled Secure Boot (MOK), auditd trails,
and atomic rollback, but 0.12.0 has not undergone an independent third-party
security audit.

Report vulnerabilities privately as described in `SECURITY.md`.

---

## License

Grintion-OS is licensed under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE). Upstream components keep their own licenses;
see [THIRD-PARTY.md](THIRD-PARTY.md).

## Network

When running in a virtual machine, set the network adapter to
`Intel PRO/1000 MT Desktop (82540EM)` so the bundled `e1000` driver is used.
