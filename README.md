# Grintion-OS

A small, source-built Linux operating system for x86_64. It boots from a
read-only squash-free initramfs, runs from an overlay in RAM, installs to a
disk with one command, and ships a package manager with signed repository
indexes.

**Minimal - Independent - Secure - Stable** (MISS)

- **Version:** 1.0.0
- **Architecture:** x86_64
- **Boot:** BIOS and UEFI (Limine 8.7.0)
- **Kernel:** Linux 6.12.114 built from kernel.org source with a hardening
  configuration fragment
- **Init:** runit
- **Userland:** GNU coreutils, glibc, bash, util-linux, PAM, OpenSSH client
- **No GUI:** the release is a console system by design

Grintion-OS 1.0.0 is built from this tree. There is no hosted binary
repository; build the ISO, or install the prerequisites and run `make`. Release
artifacts are not signed.

---

## What the system does

| Area | Behaviour |
| --- | --- |
| Live boot | Kernel and initramfs load entirely into RAM. The root is a tmpfs overlay, so the live session can write anywhere without touching a disk. |
| Installed boot | The installer copies the live root to an ext4 root partition and installs Limine for BIOS or UEFI. Root is read-write. |
| Networking | `dhcpcd` configures the first wired interface at boot. Wi-Fi tools are present (`iw`, `wpa_supplicant`) but no network manager is included. |
| Services | runit supervises two local gettys, a serial getty, networking, the nftables firewall, syslogd and a local hook. |
| Accounts | root logs in on the live image. The installer creates one administrative user in `wheel`; root stays locked unless `--root-password` is given. |
| Packages | `garb` installs, removes, upgrades and verifies `.garb` packages from Ed25519-signed repository indexes. |
| Persistence | `grintion-persist` formats a partition labelled `GRINTION_PERSIST`; the live init mounts it as the overlay upper layer, so changes survive reboot. |
| Hardening | Kernel configuration fragment (BPF syscall, kexec and `/dev/mem` off), restricted `/proc` and `dmesg`, ASLR, Yama ptrace scope, io_uring disabled by sysctl, strict network sysctls, `nftables` firewall, PAM faillock. |

Details: [architecture](docs/ARCHITECTURE.md), [installation](docs/INSTALL.md),
[package manager](docs/PACKAGE-MANAGER.md), [roadmap](docs/ROADMAP.md).

---

## Build

### Host requirements

The build host must be **Arch Linux x86_64** (or a derivative with the same
package layout). The live userland is assembled from the host's installed
packages, so the host determines the exact glibc and GNU utility versions in the
image. Other distributions are not supported by the build scripts; see
[What "independent" means](#what-independent-means).

Required commands and packages:

```sh
sudo pacman -S --needed base-devel bc bison flex kmod libarchive \
    openssl parted dosfstools e2fsprogs rsync xorriso qemu-full python \
    python-pytest python-pexpect shellcheck
```

`qemu-full` and the Python test modules are only needed for the runtime tests.
`/dev/kvm` is strongly recommended.

### Build the ISO

```sh
make            # kernel, installed initramfs, live rootfs, ISO
```

The first build compiles Linux 6.12.114 and dhcpcd, so expect a long run
(roughly 20-40 minutes on a modern 8-core host). Later builds reuse
`build/work/` and `build/cache/`. `make clean` removes build products;
`make distclean` also removes the downloaded kernel tarball.

Output:

```text
output/grintion-os-x86_64.iso
output/grintion-os-x86_64.iso.sha256
output/BUILD-INFO
output/initramfs.img
output/initramfs-install.img
output/vmlinuz-grintion
output/System.map-grintion
output/config-grintion
```

The ISO is a hybrid image: write it to a USB stick with `dd` and it boots on
BIOS and UEFI machines.

```sh
sudo dd if=output/grintion-os-x86_64.iso of=/dev/sdX bs=4M status=progress conv=fsync
```

### Verify a build

```sh
( cd output && sha256sum -c grintion-os-x86_64.iso.sha256 )
cat output/BUILD-INFO
```

`BUILD-INFO` records the pinned kernel source checksum, the kernel
configuration and image hashes, the initramfs hashes and the source commit.

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
grintion-install --unattended --disk /dev/vda \
    --hostname box --user grintion --password 'change-me'
```

Add `--dry-run` to print the plan without touching the disk. See
[docs/INSTALL.md](docs/INSTALL.md) for persistence, post-install steps and
troubleshooting.

---

## Package manager

Repositories are directories containing `.garb` packages, an `index.json` and a
detached Ed25519 signature. The client trusts only keys in
`/etc/garb/keys/*.pub` and checks the signature before reading any index entry.

```sh
garb update
garb search hello
garb info demo-hello
garb install demo-hello
garb verify
garb remove demo-hello
```

Build the demo repository from this tree:

```sh
make packages          # output/packages + unsigned index
```

Signing, the on-disk format, the threat model and current limitations are in
[docs/PACKAGE-MANAGER.md](docs/PACKAGE-MANAGER.md).

---

## Tests

```sh
make check       # syntax, config contracts, Python unit tests, package tests
make test-garb   # signed repository and transaction tests
make test-boot   # boot the ISO under BIOS and UEFI in QEMU
make test-install # install to a disk, reboot, log in, check networking
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

This is a deliberate trade-off: a small, auditable image now, with a documented
path to a from-source bootstrap later. Do not describe the image as
"from-scratch" or "built entirely from source"; it is not.

---

## Support matrix

| Feature | 1.0.0 |
| --- | --- |
| x86_64 BIOS boot | Yes, tested in QEMU |
| x86_64 UEFI boot | Yes, tested in QEMU with OVMF |
| Secure Boot | No; Limine is unsigned and there is no shim |
| ARM64 | Build scripts are x86_64-only |
| Graphical desktop | No |
| Wi-Fi | Client tools only; no DHCP or roaming daemon for wireless |
| Disk encryption | Not provided by the installer |
| Snapshots / rollback | Not provided; `garb` rolls back a failed transaction only |
| Hosted binary repository | No; `make packages` creates a local demo repository |
| Signed release artifacts | No; the ISO and `BUILD-INFO` are not signed |

Unsupported configurations are not "known broken"; they are simply outside what
this release builds and tests.

---

## Repository layout

```text
bin/            grintion-install, grintion-persist, grintion-chroot, garb, limine-deploy
build/          kernel, rootfs, initramfs and ISO build scripts
config/         kernel fragment, required binaries, PAM modules, setuid list
etc/            live and installed system configuration
init/           live-init (PID 1) and install-init (installed initramfs PID 1)
packages/       demo Garbfile packages used by the repository tests
tests/          unit and QEMU end-to-end tests
tools/          pinned build tools and sources (busybox, runit, dhcpcd, limine)
docs/           installation, build, architecture, package and verification docs
```

---

## Security

Read [SECURITY.md](SECURITY.md) before relying on this system for anything
sensitive. The short version: the design is defensive, but 1.0.0 has no Secure
Boot chain, no verified boot, no disk encryption, and no independent security
audit.

Report vulnerabilities privately as described in `SECURITY.md`.

---

## License

Grintion-OS is licensed under the GNU General Public License, version 3 or
later. See [LICENSE](LICENSE). Upstream components keep their own licenses;
see [THIRD-PARTY.md](THIRD-PARTY.md).
