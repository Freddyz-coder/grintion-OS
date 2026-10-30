# Roadmap

Grintion-OS 1.0.0 is a console-only x86_64 system with a source-built kernel, a
runit userland, a live overlay, a disk installer and a package manager with
signed repository indexes.

This page lists work that is **not** part of 1.0.0. Nothing here is a promise or
a schedule.

## Next

### Release engineering

- Sign the ISO and `BUILD-INFO` with a documented, offline release key.
- Publish a hosted, signed package repository and a documented key-rotation
  procedure.
- Make same-host builds byte-for-byte comparable and document the remaining
  host-dependent inputs.

### Installer and storage

- Optional LUKS root encryption, including a cryptsetup-capable installed
  initramfs and a serial-console unlock prompt.
- Install-time repository and trusted-key setup (`--repo`).
- Custom partitioning and dual-boot support; the current installer always
  erases the whole disk.
- Swap configuration and a documented swap-file workflow.

### Boot and platform

- Secure Boot: a signed shim/Limine chain or documented MOK enrollment. This
  cannot be claimed until it is tested on real firmware.
- ARM64 build and image pipeline. The build scripts are x86_64-only today.
- Automated bare-metal test coverage. The current matrix is QEMU only.

### Userland

- From-source userland bootstrap. This is the largest gap in the
  "independent integration" story and needs a stage0 toolchain, package build
  recipes and a source cache. Do not fake it with host copies.
- Wi-Fi boot integration: a supervised service that starts `wpa_supplicant` and
  DHCP on a wireless interface, or a small network configuration tool.
- `garb` source packages with a build sandbox, version constraints, delta
  upgrades and versioned rollback.
- Better console polish: a `dialog`-based installer and a network status view.

## Non-goals

- A graphical desktop in the base image. Window managers and desktop packages
  are not shipped in 1.0.0; the system is console-only by design.
- A general-purpose distribution with a large preinstalled application set.
- Telemetry, analytics or a mandatory online account.
- Supporting non-Arch build hosts. The live userland is curated from Arch
  packages; supporting another host means implementing and testing a different
  assembly path.

## How to propose work

Open an issue at
<https://github.com/Freddyz-coder/grintion-OS/issues> describing the problem,
the proposed scope and how it would be verified. Read
[CONTRIBUTING.md](../CONTRIBUTING.md) before sending a change.
