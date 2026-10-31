# Roadmap

Grintion-OS is an x86_64 operating system featuring a source-built kernel, a
runit userland, a live overlay, a disk installer, and dual-backend package
management (native signed repositories and bundled pacman for Arch Linux
repositories) with complete graphical desktop support via `grintion-desktop`.

This page lists work that is planned for future releases. Nothing here is a
promise or a schedule.

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

### Userland & Desktop

- Additional pre-configured desktop themes and profile presets for `grintion-desktop`.
- From-source userland bootstrap. This is the largest gap in the
  "independent integration" story and needs a stage0 toolchain, package build
  recipes and a source cache.
- Wi-Fi boot integration: a supervised service that starts `wpa_supplicant` and
  DHCP on a wireless interface, or a small network configuration tool.
- `garb` source packages with a build sandbox, version constraints, delta
  upgrades and versioned rollback.
- Better console polish: a `dialog`-based installer and a network status view.

## Non-goals

- A bloated pre-installed desktop inside the minimal base ISO. The base image
  remains lean and boots to a console prompt for pre-installation and maintenance,
  while providing seamless on-demand desktop installation via `grintion-desktop`.
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
