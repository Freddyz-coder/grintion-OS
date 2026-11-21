# Grintion-OS

A small, source-built Linux operating system for x86_64. It boots from a
read-only squash-free initramfs, runs from an overlay in RAM, installs to a
disk with one command, and ships a package manager with signed repository
indexes.

**Minimal - Independent - Secure - Stable** (MISS)

- **Version:** 0.21.0 — *custom install progress UI · live speed/size/ETA · numbered installer phases*
- **Architecture:** x86_64
- **Boot:** BIOS and UEFI (Limine 8.7.0)
- **Kernel:** Linux 6.12.114 built from kernel.org source with a hardening
  configuration fragment
- **Init:** runit
- **Userland:** GNU coreutils, glibc, bash, util-linux, PAM, OpenSSH client, GNU gzip with its full companion set
- **GUI & Desktop:** Streamlined console prompt for pre-installation, maintenance, and setup. Desktop packages and GPU drivers install with `grintion-desktop` or `garb`. XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway are verified in QEMU/KVM; GNOME is refused because `gnome-session` 51 requires the systemd user session manager
- **Audio:** HDA and USB audio are built into the kernel; desktop profiles install PipeWire, WirePlumber, firmware and the PulseAudio compatibility daemon. A shared session helper starts the stack and unmutes every detected ALSA card; it is used by the X11 hook and by XDG autostart for Wayland desktops. Playback is verified end-to-end on XFCE with QEMU audio capture

0.21.0 replaces pacman-style output with the Grintion installer and package
progress UI. `grintion-install` now shows a target banner and eight numbered
phases; installs through `grintion-desktop` and interactive `garb install`,
`upgrade`, `remove` and `update` transactions show the download size, speed,
percentage, ETA and active package instead of pacman's `::` lines. Raw package
manager output is retained in the transaction log. See
[CHANGELOG.md](CHANGELOG.md).

0.20.0 added family-level laptop hardware support for Lenovo, HP, Dell, Acer,
Asus, MSI and Samsung machines. `grintion-driver-select` matches DMI vendor
profiles and product families, loads the available ACPI/WMI/EC platform
drivers, resolves Wi-Fi, storage, audio and port firmware from each device
modalias, and installs only the missing split `linux-firmware-*` packages plus
CPU microcode, `alsa-ucm-conf` and `sof-firmware` on Intel-audio laptops.
`grintion-hcl` reports the matched family and class-level driver coverage, and
`grintion-hwinfo` reports the chassis form factor. The 0.19.0 security model
remains: boot failures halt instead of dropping to an unauthenticated root
shell, recovery requires an explicit `grintion.recovery=1` entry, every
shipped boot path selects AppArmor, enforces signed modules and requests kernel
lockdown, auditd verifies kernel auditing, and encrypted live persistence is
the default. See [CHANGELOG.md](CHANGELOG.md) and
[docs/HARDWARE-FIRMWARE.md](docs/HARDWARE-FIRMWARE.md).

0.16.0 delivered three major improvements over 0.15.0:

1. **Clean command names** — most tools in `bin/` drop the redundant
   `grintion-` prefix (e.g. `desktop`, `apparmor`, `doctor`). The rootfs build
   plants backward-compatible symlinks (`/usr/bin/grintion-<tool> → <tool>`).
   The exceptions are `mount`, `chroot`, `install`, `reset` and `ssh`, whose
   system binaries must not be shadowed; the advanced wrappers are available as
   `grintion-mount`, `grintion-chroot`, `grintion-install`, `grintion-reset`
   and `grintion-ssh`.
2. **AppArmor 2.0** — the `apparmor` tool gains AST-level brace-depth parsing,
   multi-line header support, fail-closed atomic rollback, securityfs
   cross-checking, and full flag preservation.
3. **Advanced administration** — sixteen tools (`disk`, `mount`, `swap`,
   `space`, `service`, `timer`, `dns`, `netdiag`, `firewall`, `ssh`, `cert`,
   `logs`, `load`, `bench`, `modules`, `time`) with `--json` and `--dry-run`
   support.

See [docs/COMMANDS.md](docs/COMMANDS.md) and [CHANGELOG.md](CHANGELOG.md).

Grintion-OS 0.21.0 is built from this tree. Release ISO images are published on
GitHub Releases; there is no hosted binary package repository. Build the ISO,
or install the prerequisites and run `make`. Release artifacts can be signed
with `make sign-release` and verified with `bin/release-verify` (see
[docs/REPO-KEY-CEREMONY.md](docs/REPO-KEY-CEREMONY.md)).

---

## What the system does

| Area | Behaviour |
| --- | --- |
| Live boot | Kernel and initramfs load entirely into RAM. The root is a tmpfs overlay, so the live session can write anywhere without touching a disk. |
| Installed boot | The installer copies the live root to an ext4 root partition and installs Limine for BIOS or UEFI. Root is read-write. |
| Networking | Base image: `/etc/grintion/network.conf` drives DHCP or static addressing; `grintion-network` configures static IPs and supervised Wi-Fi (`wpa_supplicant`). Desktop profiles install NetworkManager and switch `/var/service` to `/etc/sv/NetworkManager`, so the XFCE, LXQt, i3, Sway and Plasma network applets have a working D-Bus backend. DNS fallback resolvers keep name resolution responsive from early boot. |
| Laptop hardware | DMI is matched against a vendor matrix for Lenovo, HP, Dell, Acer, Asus, MSI and Samsung laptop families. `grintion-driver-select` loads the matching ACPI/WMI/EC platform modules, selects Wi-Fi, storage, audio and port drivers, and installs the missing firmware, UCM and SOF packages automatically. See [docs/HARDWARE-FIRMWARE.md](docs/HARDWARE-FIRMWARE.md). |
| Desktop & GUI | Boots to a clean prompt for pre-installation and configuration. Graphical desktop environments and GPU drivers can be pre-installed with `grintion-install --desktop` or installed on-demand with `grintion-desktop`. XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway were rendered in QEMU/KVM; GNOME is refused because `gnome-session` 51 requires systemd. |
| Audio | HDA and USB audio are built into the kernel. Desktop profiles install PipeWire, WirePlumber, firmware and ALSA tools. The shared `grintion-audio` helper is started by the X11 hook or XDG autostart, and unmutes every detected ALSA card; WirePlumber enumerates real sinks through udev instead of a hard-coded `plughw:0,0`. PipeWire playback was captured on the XFCE QEMU probe. Direct ALSA is only usable after PipeWire releases the PCM. |
| Services | runit supervises two local gettys, a serial getty, networking (dhcpcd or NetworkManager), the nftables firewall, syslogd, optional display manager, and a local hook. |
| Accounts | root logs in on the live image. The installer creates one administrative user in `wheel`; root stays locked unless `--root-password-stdin` is used. |
| Packages | `garb` installs, removes, upgrades and verifies packages via native Ed25519-signed repositories or delegating to the bundled `pacman` backend for the dated Arch snapshot. |
| Persistence | `grintion-persist` creates a LUKS2-encrypted partition labelled `GRINTION_PERSIST` (plain ext4 only with `--no-encrypt`); the live init unlocks it with a passphrase and mounts the inner ext4 filesystem as the overlay upper layer. |
| Hardening | Kernel configuration fragment, restricted `/proc` and `dmesg`, ASLR, Yama ptrace, AppArmor mandatory access control compiled into the kernel and loaded by the `apparmor` service at boot (six daemon profiles), read-only `aa-status`/`aa-unconfined` reporting, Bubblewrap application sandboxing, USBGuard data-blocking, a working `auditd` with focused rules and sudo I/O trails, mode-aware file integrity verification (`grintion-integrity`), and fail-closed security profiles (`workstation`, `server`, `kiosk`, `air-gapped`). `grintion-security set` applies the firewall, AppArmor and USB policy before writing profile state and rolls back on failure. X11 starts without TCP or abstract-socket listeners and requires a per-session cookie; `grintion-security-report` flags an exposed X server. |
| Configuration | Single unified system tool (`grintion-config`) for timezones, locales, keymaps, hostnames, user accounts, power governors, and background services. |
| Resilience | Watchdog service supervision with crash backoff, atomic package generations and rollback (`garb generations`), Btrfs snapshots with safer rollback and retention, boot-health auto-revert, automated self-healing (`grintion-selfheal`) and diagnosis (`grintion-doctor`). |

Documentation:
- [Command Reference](docs/COMMANDS.md) (every tool and subcommand — clean and legacy names)
- [Independent Release Audit](docs/INDEPENDENT-AUDIT.md) (artifact and runtime audit)
- [Handbook](docs/HANDBOOK.md) (Full 10-chapter manual)
- [Guía Rápida en Español](docs/HANDBOOK-ES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Installation](docs/INSTALL.md)
- [Security Hardening](docs/SECURITY-HARDENING.md)
- [Hardware & Firmware](docs/HARDWARE-FIRMWARE.md)
- [Hardware & Lab Validation](docs/HARDWARE-LAB.md)
- [Package Ecosystem](docs/PACKAGE-ECOSYSTEM.md)
- [32-bit and 64-bit Support](docs/MULTIARCH.md)
- [Self-Healing](docs/SELF-HEALING.md)
- [Performance Baselines](docs/PERFORMANCE-BASELINES.md)
- [Tracked Binary Provenance](docs/BINARY-PROVENANCE.md)
- [Roadmap](docs/ROADMAP.md)
- [Support and Funding](docs/SUPPORT-AND-FUNDING.md)
- [Funding Ledger](docs/FUNDING-LEDGER.md)
- [Community Support](SUPPORT.md)

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

Fresh images ship the pinned pacman sync databases, so both direct
`sudo pacman -S firefox` and `sudo garb install firefox` resolve packages
without a separate `-Sy`. On a terminal, delegated transactions use the
Grintion progress renderer; set `GRINTION_PROGRESS=1` to force it for captured
output or `GRINTION_PROGRESS=0` to keep raw output. If a custom root is missing a database, `garb`
downloads it automatically before delegating. Package names are normalized to
Arch's lowercase names, and `kde-plasma`/`network-manager` map to their Arch
packages; `garb` also maps `alsamixer` to `alsa-utils` and `nvim` to `neovim`.

Before a package transaction, `garb`, `grintion-desktop` and the installer
probe the complete Arch Linux Archive endpoints and use the faster one; pacman
runs up to ten downloads in parallel. The primary archive is the only built-in
endpoint because the former secondary served database indexes but returned 404
for package archives. The snapshot date, signatures and package versions are
unchanged.

**Backend integration:** `garb` supports dual backends:
- **Pacman backend (bundled):** Delegates to the dated Arch Linux Archive snapshot in `config/arch-snapshot` (`core`, `extra`) using the bundled `pacman` and Arch public keyrings. The snapshot matches the image's OpenSSL 3 ABI; rolling mirrors have moved to OpenSSL 4 and produce dependency conflicts.
- **Native backend:** Uses Ed25519-signed repository indexes and SHA-256 archive verification for custom packages.

```sh
garb update                      # Refresh the dated snapshot databases
                                 # (the first install syncs automatically)
garb search jq                   # Search packages
garb info jq                     # Package metadata
sudo garb install jq             # Install package and dependencies
garb verify                      # Verify file integrity
garb list                        # List native-backend packages
garb list --upgradable           # Native-backend upgrades
sudo garb clean                  # Purge the native repository cache
sudo garb remove jq              # Remove package
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
grintion-desktop list                # View supported desktop environments
sudo grintion-desktop install xfce    # Fast & lightweight traditional desktop (Recommended)
sudo grintion-desktop install kde     # KDE Plasma - verified Wayland session
sudo grintion-desktop install lxqt    # Ultra-lightweight Qt desktop (verified)
sudo grintion-desktop install sway    # Wayland tiling compositor (verified)
sudo grintion-desktop drivers         # Auto-detect GPU and install graphics drivers
```

LightDM and SDDM are supervised by runit (`/var/service/display-manager`); GDM is not used because it requires systemd-logind. See [docs/DESKTOP-GUI.md](docs/DESKTOP-GUI.md) for full instructions.

---

## Laptop hardware support

Grintion-OS recognizes laptop families from **Lenovo, HP, Dell, Acer, Asus,
MSI and Samsung** using DMI vendor aliases and product-family globs. The
matrix lives in [`etc/grintion/laptop-support.json`](etc/grintion/laptop-support.json),
so a family entry covers every model in that family rather than one tested SKU.

| Vendor | Covered families | Platform drivers |
| --- | --- | --- |
| Lenovo | ThinkPad, ThinkBook, IdeaPad, Legion, LOQ, Yoga, V/Slim | `thinkpad_acpi`, `think_lmi`, `ideapad_laptop` |
| HP | EliteBook, ProBook, ZBook, Dragonfly, Pavilion, Envy, Spectre, OMEN, Victus | `hp_wmi`, `hp_accel` |
| Dell | Latitude, Vostro, Inspiron, XPS, Precision, G-Series, Alienware | `dell_laptop`, `dell_wmi`, `dell_smbios` |
| Acer | Aspire, Nitro, Predator, Swift, Spin, TravelMate, Extensa, ConceptD | `acer_wmi`, `acer_wireless`, `acerhdf` |
| Asus | ZenBook, VivoBook, ProArt, ROG, TUF, ExpertBook | `asus_wmi`, `asus_nb_wmi`, `asus_laptop` |
| MSI | Prestige, Modern, Creator, Katana, Raider, Stealth, Vector, Thin | `msi_ec`, `msi_wmi`, `msi_wmi_platform` |
| Samsung | Galaxy Book, Notebook, Odyssey, Galaxy Chromebook, 300E/500R5/700G/900X | `samsung_laptop`, `samsung_q10` |

The installer runs `grintion-driver-select --apply` automatically. It detects
Wi-Fi, NVMe/SATA/UFS storage, card readers, HDA/SOF audio and USB4/Thunderbolt
controllers, asks `modinfo` which firmware each module needs, and installs only
the missing split firmware packages plus CPU microcode, `alsa-ucm-conf` and
`sof-firmware` on Intel-audio machines. It writes
`/etc/grintion/hardware-profile.json` and
`/etc/modules-load.d/grintion-hardware.conf`. `--no-auto-drivers` skips the
step, and an offline install leaves the exact package list in the manifest.

```sh
grintion-hcl                         # vendor family, compatibility, Wi-Fi/storage/audio/ports
grintion-driver-select --json        # detected modules, firmware gaps and packages
sudo grintion-driver-select --apply  # install the selected support now
grintion-firmware status             # EFI firmware/ESRT entries
```

This is driver-level support added in 0.20.0. Physical per-model validation
remains tracked in [docs/HARDWARE-LAB.md](docs/HARDWARE-LAB.md); a model that is
not listed in the lab still receives the generic drivers and firmware path.

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
- The optional `pacman` backend installs Arch packages from the dated Arch
  Linux Archive snapshot in `config/arch-snapshot`. It is an explicit Arch
  dependency, not independent packaging.

This is a deliberate trade-off: a small, auditable image now, with a documented
path to a from-source bootstrap later. Do not describe the image as
"from-scratch" or "built entirely from source"; it is not.

---

## Support matrix

| Feature | 0.21.0 |
| --- | --- |
| x86_64 BIOS boot | Yes, tested in QEMU. Bare-metal lab logs are not published; see [docs/VERIFICATION.md](docs/VERIFICATION.md). |
| x86_64 UEFI boot | Yes, tested in QEMU with OVMF. Bare-metal lab logs are not published; see [docs/VERIFICATION.md](docs/VERIFICATION.md). |
| Bare-metal hardware | A 0.21.0 host probe on a Lenovo IdeaPad Flex 5 16ABR8 verified DMI detection, HCL coverage and driver/firmware selection without changing disks. No bare-metal install or reboot was performed; the QEMU installer tests exercise the install path. See [docs/VERIFICATION.md](docs/VERIFICATION.md). |
| 32-bit userspace | Yes on 64-bit machines through `CONFIG_IA32_EMULATION` and `grintion-install --compat32`; 32-bit-only CPUs are refused by the x86_64 image. See [docs/MULTIARCH.md](docs/MULTIARCH.md). |
| Secure Boot | Supported via local MOK keys (`grintion-secureboot`) & UKI (`grintion-uki`); pre-enrolled Microsoft 3rd-party CA shim is not bundled (see [docs/SECURE-BOOT.md](docs/SECURE-BOOT.md)) |
| ARM64 | Build scripts are x86_64-only |
| Graphical desktop | XFCE, i3, KDE Plasma (Wayland/SDDM), LXQt (LightDM/X11) and Sway are verified in QEMU/KVM. GNOME is not supported because `gnome-session` 51 requires `org.freedesktop.systemd1` |
| Kernel flavors | LTS (`6.12.114-grintion`) is the default source-built kernel. The installer and `grintion-kernel` can optionally add `hwe` (Arch current kernel + headers) or `dkms` (HWE headers + module builds) from the pinned snapshot as separate Limine entries. HWE/DKMS require network access and are not boot-verified in this tree. |
| Audio | HDA and USB audio are built in. Intel SOF (Tiger Lake through Panther Lake) and SoundWire, AMD ACP3x/5x/6x, and Realtek/Conexant/Sigmatel codecs are enabled. Laptop installs add `alsa-ucm-conf` and, on Intel audio, `sof-firmware`. PipeWire playback was verified end-to-end on XFCE (QEMU WAV capture); direct ALSA requires suspending PipeWire first |
| Wi-Fi | Kernel contract covers Intel `iwlwifi`, Realtek `rtw88`/`rtw89`, MediaTek `mt76`, Qualcomm Atheros and Broadcom `brcmfmac`. `grintion-driver-select` installs only the split `linux-firmware-*` package a detected card needs. `grintion-network` provides Enterprise WPA2/WPA3, priority roaming, reconnection, MAC randomization and a DNS leak test |
| Laptop hardware | Lenovo, HP, Dell, Acer, Asus, MSI and Samsung families are matched from DMI; vendor ACPI/WMI/EC modules, storage, audio, port and firmware support are installed automatically. See [docs/HARDWARE-FIRMWARE.md](docs/HARDWARE-FIRMWARE.md) |
| Storage | NVMe over PCIe, SATA AHCI, UFS, SDHCI and Realtek RTSX card readers are in the kernel contract; card-reader and removable-media modules are selected from detected hardware |
| Ports | USB4/Thunderbolt 3 and 4, USB-C UCSI and DisplayPort alternate mode, USB 3.x/2.0, HDMI/DisplayPort, SD/microSD readers and 3.5 mm audio are covered |
| Disk encryption | Supported; LUKS2 root (`--encrypt`), encrypted swap (`/etc/sv/cryptswap`), encrypted `/home` (`--encrypt-home`) via `grintion-install`, and LUKS2 live persistence via `grintion-persist` |
| Snapshots / rollback | Supported; Btrfs root snapshots and rollback (`grintion-snapshot`), boot failure auto-rollback (`grintion-boot-health`), and package generations (`garb generations` / `rollback-generation`) |
| Package installation | Supported; dual backends (`garb` native signed repo & bundled `pacman` with the dated Arch snapshot). The image ships the snapshot sync databases, so direct `pacman -S` works without a separate `-Sy`. Seeded packages own their complete shared-library sets and unowned udev/desktop data is pruned, so Firefox and desktop installs do not fail on file conflicts or missing `.so` files. |
| Hosted binary repository | **No repository is hosted.** Release channels, delta updates and signed index metadata exist as tooling; the README does not claim a public server. |
| Signed release artifacts | Tooling and a tag-triggered release workflow exist. Released images are unsigned because no release key is available; verify their SHA-256. `build/sign-release.sh` signs `SHA256SUMS` and `BUILD-INFO`, verified via `grintion-release-verify` (see [docs/REPO-KEY-CEREMONY.md](docs/REPO-KEY-CEREMONY.md)) |

Unsupported configurations are not "known broken"; they are simply outside what
this release builds and tests.

---

## Repository layout

```text
bin/            install, config, desktop, persist, chroot, garb, limine-deploy,
                doctor, security-report, hwinfo, hcl, driver-select, firmware,
                release-verify, release-audit,
                secureboot, uki,
                attest, tpm-luks, snapshot, boot-health, backup, reset, network,
                session, audit, integrity, audit-log, sandbox, shield, vault, usb,
                watchdog, tour, help, report, welcome, apparmor, aa-status,
                aa-unconfined, disk, mount, swap,
                space, service, timer, dns, netdiag, firewall, ssh, cert, logs,
                load, bench, modules, time
                (legacy grintion-<name> symlinks auto-created in rootfs)
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

## Support and community

Grintion-OS is maintained without ads, telemetry or vendor funding. If it is
useful to you, you can fund the CI hardware, signing keys and hosting that the
release process depends on, or contribute test evidence instead:

- [Support the project](docs/SUPPORT-AND-FUNDING.md) - funding channels, what the money pays for, and the funding policy
- [Funding ledger](docs/FUNDING-LEDGER.md) - recorded income and spend
- [SUPPORT.md](SUPPORT.md) - where to ask questions and report problems
- [Contributing](CONTRIBUTING.md) - build, test and patch rules

The public page is generated from `site/` by the `Support site` workflow; see
[the setup guide](docs/SUPPORT-AND-FUNDING.md) for the Pages configuration.

---

## Security

Read [SECURITY.md](SECURITY.md) before relying on this system for anything
sensitive. The short version: the design is defensive and implements LUKS2
encryption, AppArmor MAC, user-controlled Secure Boot (MOK), auditd trails,
and atomic rollback, but 0.21.0 has not undergone an independent third-party
security audit. The automated `grintion-release-audit` checks are documented in
[docs/INDEPENDENT-AUDIT.md](docs/INDEPENDENT-AUDIT.md); they are not a
substitute for external review.

Report vulnerabilities privately as described in `SECURITY.md`.

---

## License

Grintion-OS is licensed under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE). Upstream components keep their own licenses;
see [THIRD-PARTY.md](THIRD-PARTY.md).

## Network

When running in a virtual machine, set the network adapter to
`Intel PRO/1000 MT Desktop (82540EM)` so the bundled `e1000` driver is used.
