# Grintion-OS

A small, source-built Linux operating system for x86_64. It boots from a
read-only squash-free initramfs, runs from an overlay in RAM, installs to a
disk with one command, and ships a package manager with signed repository
indexes.

**Minimal - Independent - Secure - Stable** (MISS)

- **Version:** 0.9.0
- **Architecture:** x86_64
- **Boot:** BIOS and UEFI (Limine 8.7.0)
- **Kernel:** Linux 6.12.114 built from kernel.org source with a hardening
  configuration fragment
- **Init:** runit
- **Userland:** GNU coreutils, glibc, bash, util-linux, PAM, OpenSSH client
- **GUI & Desktop:** Streamlined console prompt for pre-installation, maintenance, and setup. Desktop packages (XFCE, GNOME, KDE Plasma, Sway, LXQt, i3) and GPU drivers install with `grintion-desktop` or `garb`; XFCE and i3 are verified in QEMU/KVM with keyboard and pointer input, while KDE Plasma, GNOME, LXQt and Sway remain unverified
- **Audio:** HDA and USB audio are built into the kernel; desktop profiles install PipeWire, WirePlumber and the PulseAudio compatibility daemon, started by the X11 session hook. Playback is verified end-to-end on XFCE and i3 with QEMU audio capture

Grintion-OS 0.9.0 is built from this tree. There is no hosted binary
repository; build the ISO, or install the prerequisites and run `make`. Release
artifacts are not signed.

---

## What the system does

| Area | Behaviour |
| --- | --- |
| Live boot | Kernel and initramfs load entirely into RAM. The root is a tmpfs overlay, so the live session can write anywhere without touching a disk. |
| Installed boot | The installer copies the live root to an ext4 root partition and installs Limine for BIOS or UEFI. Root is read-write. |
| Networking | `/etc/grintion/network.conf` drives DHCP or static addressing; `grintion-network` configures static IPs and supervised Wi-Fi (`wpa_supplicant`). DNS fallback resolvers keep name resolution responsive from early boot. |
| Desktop & GUI | Boots to a clean prompt for pre-installation and configuration. Graphical desktop environments (XFCE, GNOME, KDE Plasma, Sway, LXQt, i3) and GPU drivers can be pre-installed with `grintion-install --desktop` or installed on-demand with `grintion-desktop`. XFCE and i3 (LightDM + Xorg) were rendered with working keyboard and pointer input in QEMU/KVM; KDE Plasma, GNOME, LXQt and Sway remain unverified. |
| Audio | HDA and USB audio are built into the kernel. Desktop profiles install PipeWire, WirePlumber, `pipewire-pulse` and ALSA tools; the X11 session hook starts them and unmutes the card. A static `plughw:0,0` sink replaces udev enumeration. Playback through PipeWire and direct ALSA was verified on the i3 and XFCE probes. |
| Services | runit supervises two local gettys, a serial getty, networking, the nftables firewall, syslogd, optional display manager, and a local hook. |
| Accounts | root logs in on the live image. The installer creates one administrative user in `wheel`; root stays locked unless `--root-password-stdin` is used. |
| Packages | `garb` installs, removes, upgrades and verifies packages via native Ed25519-signed repositories or delegating to the bundled `pacman` backend for Arch official packages. |
| Persistence | `grintion-persist` formats a partition labelled `GRINTION_PERSIST`; the live init mounts it as the overlay upper layer, so changes survive reboot. |
| Hardening | Kernel configuration fragment (BPF syscall, kexec and `/dev/mem` off), restricted `/proc` and `dmesg`, ASLR, Yama ptrace scope, binfmt_misc compiled out, io_uring disabled at runtime, signed modules only, strict network sysctls, `nftables` firewall, PAM faillock. |

Details: [architecture](docs/ARCHITECTURE.md), [installation](docs/INSTALL.md),
[desktop & GUI](docs/DESKTOP-GUI.md), [package manager](docs/PACKAGE-MANAGER.md), [roadmap](docs/ROADMAP.md).

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

> **Verification status:** package transactions, D-Bus accounts, the
> display-manager service and desktop audio are verified. XFCE and i3
> (LightDM + Xorg) were rendered in QEMU/KVM with working keyboard and pointer
> input, and a 440 Hz tone played through PipeWire was captured from the
> emulated HDA device. KDE Plasma, GNOME, LXQt and Sway remain unverified; see
> [docs/VERIFICATION.md](docs/VERIFICATION.md).

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
grintion-desktop install gnome      # Modern Wayland desktop suite
grintion-desktop install kde        # KDE Plasma - customizable and modular
grintion-desktop install sway       # Lightweight Wayland tiling compositor
grintion-desktop install lxqt       # Ultra-lightweight Qt desktop
grintion-desktop drivers            # Auto-detect GPU and install graphics drivers
```

Supported display managers (LightDM, SDDM, GDM) are supervised by runit (`/var/service/display-manager`). See [docs/DESKTOP-GUI.md](docs/DESKTOP-GUI.md) for full instructions.

---

## Tests

```sh
make check       # syntax, config contracts, Python unit tests, package tests
make test-garb   # signed repository and transaction tests
make test-boot   # boot the ISO under BIOS and UEFI in QEMU
make test-network # boot five virtual NIC models under BIOS/QEMU
make test-install # install to a disk, reboot, log in, check networking
make test-install-uefi # install under UEFI/OVMF and reboot from it
make test-all    # all of the above
```

The runtime tests need KVM and OVMF (`edk2-ovmf`). Exact coverage and the
results recorded for this release are in [docs/VERIFICATION.md](docs/VERIFICATION.md).

---

## What "independent" means

Grintion-OS is independent in **integration**, not in the sense of writing every
component from scratch:

- The kernel, bootloader, init, C library and base utilities are upstream
  projects, used unmodified except for configuration.
- The live userland is **not** built from source by this repository. It is a
  curated copy of the build host's packages, with every required command listed
  in `config/rootfs.required-binaries` and every shared library resolved
  explicitly.
- `garb` packages are prebuilt file trees. There is no source build recipe, no
  compiler toolchain in the image, and no cross-compilation.
- The optional `pacman` backend installs Arch packages from official
  repositories. It is an explicit Arch dependency, not independent packaging.

This is a deliberate trade-off: a small, auditable image now, with a documented
path to a from-source bootstrap later. Do not describe the image as
"from-scratch" or "built entirely from source"; it is not.

---

## Support matrix

| Feature | 0.9.0 |
| --- | --- |
| x86_64 BIOS boot | Yes, tested in QEMU |
| x86_64 UEFI boot | Yes, tested in QEMU with OVMF |
| Secure Boot | No; Limine is unsigned and there is no shim |
| ARM64 | Build scripts are x86_64-only |
| Graphical desktop | XFCE and i3 verified in QEMU/KVM (LightDM/Xorg, keyboard and pointer, rendered frame); KDE Plasma, GNOME, LXQt and Sway unverified |
| Audio | PipeWire playback verified end-to-end on XFCE and i3 (QEMU WAV capture), plus direct ALSA playback; PipeWire 1.6.10's `pipewire-alsa` client can hang on drain (fixed upstream in 1.6.11) |
| Wi-Fi | `grintion-network` writes the `[wifi]` config and enables the supervised `wpa_supplicant` service |
| Disk encryption | Not provided by the installer |
| Snapshots / rollback | Not provided; `garb` rolls back a failed transaction only |
| Package installation | Supported; dual backends (`garb` native signed repo & bundled `pacman` with Arch official repos) |
| Hosted binary repository | No Grintion-hosted repository; the pacman backend uses Arch official repositories |
| Signed release artifacts | No; the ISO and `BUILD-INFO` are not signed |

Unsupported configurations are not "known broken"; they are simply outside what
this release builds and tests.

---

## Repository layout

```text
bin/            grintion-install, grintion-desktop, grintion-persist, grintion-chroot, garb, limine-deploy, grintion-doctor
build/          kernel, rootfs, initramfs and ISO build scripts
config/         kernel fragment, required binaries, PAM modules, setuid list
etc/            live and installed system configuration
init/           live-init (PID 1) and install-init (installed initramfs PID 1)
packages/       demo Garbfile packages used by the repository tests
tests/          unit and QEMU end-to-end tests
tools/          pinned build tools and sources (busybox, runit, dhcpcd, limine)
docs/           installation, desktop & GUI, build, architecture, package and verification docs
```

---

## Security

Read [SECURITY.md](SECURITY.md) before relying on this system for anything
sensitive. The short version: the design is defensive, but 0.9.0 has no Secure
Boot chain, no verified boot, no disk encryption, and no independent security
audit.

Report vulnerabilities privately as described in `SECURITY.md`.

---

## License

Grintion-OS is licensed under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE). Upstream components keep their own licenses;
see [THIRD-PARTY.md](THIRD-PARTY.md).

## Network

When running in a virtual machine, set the network adapter to
`Intel PRO/1000 MT Desktop (82540EM)` so the bundled `e1000` driver is used.
