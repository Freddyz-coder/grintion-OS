# Building Grintion-OS

This document covers building the 0.12.1 ISO from source. Installation is in
[INSTALL.md](INSTALL.md); the boot flow is in [ARCHITECTURE.md](ARCHITECTURE.md).

The build is **offline after the first fetch**. `make tools` and `make kernel`
download pinned archives into `build/cache/`, verify their SHA-256, and reuse
them on later runs.

---

## Host requirements

The build host must be **Arch Linux x86_64** (or a derivative with the same
package names and paths). `build/make-rootfs.sh` copies the host's glibc,
coreutils, bash, util-linux, PAM and OpenSSL packages into the live image. A
different distribution will either fail the required-command check or produce an
image with an unexpected userland.

For a reproducible patch level, use `make rootfs-pinned`. It runs
`build/make-rootfs.sh` inside a container whose packages come from the dated
Arch Linux Archive snapshot in `config/arch-snapshot`; the host userland is then
irrelevant. The plain `make rootfs` path remains available for fast local
iteration but is not the release path.

```sh
sudo pacman -S --needed base-devel bc bison flex kmod cpio gzip curl \
    openssl parted dosfstools e2fsprogs rsync xorriso \
    pacman gnupg archlinux-keyring apparmor \
    python python-pytest python-pexpect \
    qemu-full edk2-ovmf shellcheck
```

If the build host cannot install `apparmor`, download its package and point the
rootfs build at the unpacked tree. The parser and policy abstractions are copied
into the image; the package is not needed system-wide:

```sh
mkdir -p build/work/apparmor-root
curl -fL -o build/work/apparmor.pkg.tar.zst "$(pacman -Sp apparmor)"
bsdtar -xf build/work/apparmor.pkg.tar.zst -C build/work/apparmor-root
GRINTION_APPARMOR_ROOT="$PWD/build/work/apparmor-root" make rootfs
```

The resulting `make check` gate still runs on hosts without AppArmor.

What each group is for:

| Package | Used by |
| --- | --- |
| `apparmor` | `make rootfs`: supplies `apparmor_parser` and the policy abstractions; the build fails without it. `make check` does not require it. |
| `base-devel`, `bison`, `flex`, `kmod` | kernel build, `depmod` |
| `bc` | kernel build (a pinned copy is also built into `tools/bin/bc`) |
| `cpio`, `gzip` | live rootfs staging checks |
| `curl` | `build/build-tools.sh` downloads |
| `openssl` | `garb` signatures and installer |
| `parted`, `dosfstools`, `e2fsprogs`, `rsync` | installer and installed initramfs |
| `xorriso` | ISO creation |
| `python`, `python-pytest`, `python-pexpect` | build scripts, tests |
| `qemu-full`, `edk2-ovmf` | runtime tests only |
| `shellcheck` | `make check` lint (required; the gate fails without it) |
| `pacman`, `gnupg`, `archlinux-keyring` | optional pacman backend, keyring and gpg helpers copied into the image |

`/dev/kvm` is strongly recommended for runtime tests. Without it the tests still
run under TCG but take much longer.

The live image also carries the optional pacman backend. `build/make-rootfs.sh`
copies `/etc/pacman.conf`, the public Arch keyring, the keyring sources and gpg
helpers, then runs `build/seed-pacman-db.py` to seed pacman's local database
from the build host. The seed step is what prevents `pacman -S` from trying to
reinstall glibc over the curated rootfs. The script also creates
`/etc/mtab` as a symlink to `/proc/self/mounts`, which pacman's `CheckSpace`
needs to monitor available storage. See [PACKAGE-MANAGER.md](PACKAGE-MANAGER.md).

---

## Targets

```sh
make help
```

| Target | Result |
| --- | --- |
| `make tools` | Downloads, verifies and builds busybox 1.37.0, runit 2.1.2, bc 1.07.1 and dhcpcd 10.5.2 into `tools/`. |
| `make kernel` | Builds Linux 6.12.114 with `config/kernel-hardened.config`; writes `output/vmlinuz-grintion`, `System.map-grintion`, `config-grintion`, `output/licenses/linux/COPYING` and `output/kernel-BUILD-INFO`. |
| `make install-initramfs` | Builds the tiny busybox + `e2fsck` initramfs used by installed disks: `output/initramfs-install.img`. |
| `make rootfs` | Assembles the live root from host packages and packs it into `output/initramfs.img`. Depends on `tools`, `kernel` and `install-initramfs`. |
| `make rootfs-pinned` | Builds the same rootfs inside the dated Arch Linux Archive container from `config/arch-snapshot`. Use this for releases. |
| `make iso` | Creates `output/grintion-os-x86_64.iso`, installs the Limine BIOS record, writes `BUILD-INFO` and the `.sha256`. |
| `make check` | Static gate: shell syntax, shellcheck (required), tracked-binary hashes, Python compilation, executable bits, host commands, doc links, absolute paths, `garb` tests. It does not run pacman against the network. |
| `make check-upstream` | Reports whether a newer 6.12.x kernel exists on kernel.org; run weekly by CI. |
| `make test-garb` | `make check` plus the package-manager suite (included in check already). |
| `make test-boot` | QEMU live boot on BIOS and UEFI. |
| `make test-install` | QEMU install to a disk, reboot, log in, verify. |
| `make packages` | Builds the demo packages and an **unsigned** index into `output/packages/`. |
| `make clean` | Removes `build/work/`, `output/` and `dist/`. |
| `make distclean` | Also removes `build/cache/`. |
| `make release` | Runs `check` and `iso`, then prints checksums and suggested `git tag`/`gh release` commands. |

`make` alone is equivalent to `make iso`.

### First build

```sh
make            # roughly 20-40 minutes on a modern 8-core host
```

The kernel is the long pole. Later `make iso` runs reuse the kernel build in
`build/work/linux-6.12.114` and the extracted tool sources in `tools/src`.

### Individual stages

```sh
make tools
make kernel
make install-initramfs
make rootfs
make iso
```

`make rootfs` requires all three preceding artifacts. Running it directly on a
fresh tree fails with a clear message naming the missing file.

---

## Pinned inputs and verification

| Input | Pin | Verification |
| --- | --- | --- |
| Linux kernel | 6.12.114 | `config/linux-6.12.114.tar.xz.sha256`, from kernel.org's signed `sha256sums.asc` |
| busybox | 1.37.0 | `config/tools.sha256` |
| runit | 2.1.2 | `config/tools.sha256` |
| bc | 1.07.1 | `config/tools.sha256` |
| dhcpcd | 10.5.2 | `config/tools.sha256` |
| Limine | 8.7.0 | Assets vendored under `tools/limine/`, hashes in `config/binaries.sha256` |
| runit/busybox/bc/dhcpcd tarballs | pinned versions | `config/tools.sha256` (verified before extraction) |
| Tracked runit/xorriso/Limine binaries | see [BINARY-PROVENANCE.md](BINARY-PROVENANCE.md) | `config/binaries.sha256`, checked by every `make check` |
| Live userland | dated ALA snapshot | `config/arch-snapshot` and `build/rootfs-container/Containerfile` |

`build/kernel.sh` refuses to configure the kernel if a required symbol is
missing after merging the fragment; the contract is enforced by
`build/check-kernel-config.sh`. The generated `.config` hash is recorded in
`output/kernel-BUILD-INFO`.

To inspect the kernel contract:

```sh
grep -E 'CONFIG_(BPF_SYSCALL|IO_URING|USER_NS|KEXEC|HIBERNATION|DEVMEM|STRICT_DEVMEM|SECURITY_YAMA|HARDENED_USERCOPY)' config/kernel-hardened.config
```

---

## Environment and timestamps

`build/lib.sh` exports:

- `SOURCE_DATE_EPOCH=1767225600` (2026-01-01 UTC) unless already set;
- `LC_ALL=C`, `TZ=UTC`, `umask 022`;
- `PATH` with `tools/bin` first, so pinned tools win over host versions.

`build/kernel.sh` additionally pins `KBUILD_BUILD_USER`, `KBUILD_BUILD_HOST`,
`KBUILD_BUILD_VERSION` and `KBUILD_BUILD_TIMESTAMP`.

`build/mkinitramfs.py` writes a deterministic newc archive: fixed mtimes, uid
and gid 0, sorted entries, no gzip timestamp. `garb` uses the same epoch for
package metadata and zeroes the gzip mtime.

**The ISO is not yet bit-for-bit reproducible across hosts.** `make rootfs-pinned`
removes the host userland as a variable, but `BUILD-INFO` records the builder
and host kernel, and `build-iso.sh` does not normalize ISO file dates. Same-host
rebuilds are close but are not currently compared by the test suite. Do not
claim cross-host reproducibility until `build/check-reproducibility.sh` records
a matching pair.

---

## Updating a pinned version

The kernel and build tools are pinned by hand. The weekly
`Upstream kernel watch` workflow runs `make check-upstream` and fails when a
newer 6.12.x release exists. To bump it:

1. Download the new tarball from kernel.org and take the SHA-256 from the signed
   `sha256sums.asc` list.
2. Update `KERNEL_VERSION` and `SOURCE_URL` in `build/kernel.sh`, replace the
   `config/linux-*.tar.xz.sha256` file, and update the version in this document,
   `README.md`, `SECURITY.md` and `THIRD-PARTY.md`.
3. Run `make kernel`, then `make rootfs-pinned` and `make check`.
4. For a tool bump, update the filename/version and hash in
   `config/tools.sha256`, then run `make tools`. Re-run `sha256sum tools/bin/*`
   and update `config/binaries.sha256` if a tracked binary changed.

---

## Offline builds

After one successful `make`:

- kernel tarball: `build/cache/linux-6.12.114.tar.xz`
- tool tarballs: `build/cache/tools/`
- extracted sources: `build/work/linux-6.12.114/`, `tools/src/`
- built tools: `tools/bin/`

`build/build-tools.sh` skips a download when the archive already exists, but it
always verifies the checksum. To force a re-download, delete the specific file
or run `make distclean`.

---

## Cleaning

```sh
make clean        # build/work + output + dist; keeps downloads and tools
make distclean    # also removes build/cache
rm -rf tools/src  # re-extracted by make tools
```

`make clean` does **not** remove `tools/bin`; they are cheap to keep and needed
by `make rootfs`. Removing `tools/bin/busybox` or `tools/bin/bc` requires
`make tools` again.

---

## Troubleshooting

**`required host binaries are missing: ...`**
`config/rootfs.required-binaries` lists every command the live image must have.
Install the matching Arch package; the build deliberately fails rather than
silently shipping a partial image.

**`tools/bin/busybox is missing; run make tools`**
`make rootfs` was run before `make tools`, or `tools/bin` was cleaned. Run
`make tools`.

**`pam_unix.so missing from rootfs` / `dynamic loader missing`**
`build/resolve-libs.py` did not find a host library. Confirm `pam` and `glibc`
are installed and that `ldd` works on the host.

**Kernel config validation fails**
Some required option was dropped by `olddefconfig`, usually because a
dependency is unavailable. The error names the symbol. Fix the fragment or the
host toolchain; do not remove the check.

**ISO builds but does not boot**
Re-run `make iso` after `make kernel` so the ISO tree gets the current
`vmlinuz-grintion`. Check `output/BUILD-INFO` hashes match the files in the ISO
tree.

**No KVM**
`make test-boot` and `make test-install` print a warning and use TCG. They are
much slower and may need longer pexpect timeouts; treat a timeout under TCG as
inconclusive, not as a product failure.
