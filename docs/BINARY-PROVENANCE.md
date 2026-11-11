# Tracked binary provenance

`config/binaries.sha256` pins every binary committed to this repository.
`build/check.sh` runs `sha256sum -c` over that file, so a changed binary fails
the gate until the hash and this document are updated in the same commit.

This is a provenance record, not a claim that every binary is built from source
by this repository. The build is honest about which parts are upstream blobs.

| Path | Provenance | Build / verification |
| --- | --- | --- |
| `tools/bin/runit`, `runsv`, `runsvdir`, `sv`, `chpst` | runit 2.1.2, <https://smarden.org/runit/> | Built by `build/build-tools.sh` from `runit-2.1.2.tar.gz`; the tarball SHA-256 is in `config/tools.sha256` and is checked before extraction. HTTPS is used for the download. |
| `tools/bin/xorriso` | GNU xorriso 1.5.6.pl02 (libburnia), from the Arch Linux `xorriso` package | Vendored executable. No source tarball is pinned for this binary yet; `build/build-iso.sh` prefers this copy so the ISO tooling version does not drift with the host. |
| `tools/limine/*` (except `BOOTAA64.EFI`) | Limine 8.7.0, <https://github.com/limine-bootloader/limine/releases/tag/v8.7.0> | Upstream prebuilt release assets. Hashes are pinned here; `bin/limine-deploy`, `build/build-iso.sh` and `build/make-rootfs.sh` install the same files. |
| `tools/limine/BOOTAA64.EFI` | Removed | ARM64 is not a supported architecture for this release. Shipping the binary implied support that does not exist. |

## What is not covered

- The kernel and dhcpcd are built from source during `make kernel` and
  `make tools`; their tarballs are pinned in `config/linux-6.12.114.tar.xz.sha256`
  and `config/tools.sha256`.
- busybox and bc are also built from pinned tarballs but are gitignored because
  `make tools` recreates them locally.
- The live userland comes from the build environment. `make rootfs-pinned`
  builds it inside the dated Arch Linux Archive snapshot recorded in
  `config/arch-snapshot`; see [BUILDING.md](BUILDING.md).

## Updating a pinned binary

1. Replace the file from the upstream release or rebuild it from the pinned
   tarball.
2. Run `sha256sum tools/bin/<name>` (or the full path) and update
   `config/binaries.sha256`.
3. Update the provenance row above with the upstream version and URL.
4. Run `make check`; the provenance check must pass.
