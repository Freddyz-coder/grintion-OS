# Architecture

Grintion-OS 1.0.0 is a console-only x86_64 system built around a source-built
Linux kernel, a runit userland, and a read-only live root that can be overlaid
with RAM or persistent storage. This document describes the moving parts and
the reasoning behind the unusual ones.

```text
BIOS/UEFI
   |
Limine 8.7.0
   |
Linux 6.12.114-grintion
   |
   +-- live:      /init (initramfs) -> overlay -> chroot -> runit
   +-- installed: /init (tiny initramfs) -> mount root -> switch_root -> runit
```

---

## 1. Boot media

`build/build-iso.sh` builds a hybrid ISO9660 image with Limine:

- BIOS: `limine-bios-cd.bin` plus a Limine BIOS boot record written into the
  image by `limine bios-install`.
- UEFI: `limine-uefi-cd.bin` and `EFI/BOOT/BOOTX64.EFI`.

The ISO tree contains exactly the bootloader assets, `limine.conf`,
`vmlinuz-grintion`, `initramfs.img` and `BUILD-INFO`. There is no squashfs and
no second-stage media lookup: the live root is inside `initramfs.img`.

Two menu entries share the same kernel and initramfs:

| Entry | Command line | Purpose |
| --- | --- | --- |
| live | `rdinit=/init quiet ...` | normal live boot |
| recovery shell | `rdinit=/bin/sh quiet` | shell before any overlay or service starts |

Both add `console=tty0 console=ttyS0,115200` so the image is testable and
usable headless over serial.

---

## 2. Live boot

`init/live-init` is `/init` inside the live initramfs.

1. Mount `proc`, `sys`, `devtmpfs`, `devpts`, `shm`, `/run`, cgroup v2 and
   `efivarfs` when present.
2. Look for a filesystem labelled `GRINTION_PERSIST`:

   ```sh
   PERSIST_DEV="$(blkid -L GRINTION_PERSIST)"
   ```

   If it mounts read-write, its `upper/` and `work/` directories become the
   overlay upper layer. Otherwise a tmpfs under `/run/overlay` is used and the
   session is discarded on poweroff.
3. Bind-mount the initramfs root on `/lower` and mount an overlay on `/newroot`:

   ```text
   lowerdir=/lower          (read-only initramfs)
   upperdir=/run/persist/upper   or /run/overlay/upper
   workdir=.../work
   ```

4. Make the mount tree private, move `proc`, `sys`, `dev` and `run` into the new
   root.
5. `exec chroot /newroot /sbin/init`.

### Why `chroot` instead of `switch_root`

`switch_root` deletes the contents of the old root and mounts the new root in
its place. The old root here **is the overlay's lower layer**; deleting it would
pull the filesystem out from under the running system. `chroot` keeps the
initramfs mounted and hidden behind the new process root. PID 1 is the chroot
process, which `exec`s runit, satisfying runit's requirement to be PID 1.

`/sbin/init` is a symlink to `/usr/sbin/runit` because the image uses a
merged-`/usr` layout (`/bin`, `/sbin`, `/lib`, `/lib64` are symlinks into
`/usr`).

### Live login

`/etc/sv/agetty-tty1/run` detects `/etc/grintion/live`. On the live image it
starts `agetty` with `--login-program /usr/bin/live-shell`; `live-shell` runs
`setsid -w -c /bin/bash -l`, giving a root shell with job control and no PAM
password prompt. This is deliberate for an ephemeral live medium, not a
configuration to copy to an installed system. On an installed system the same
service runs plain `agetty` and `login(1)` with the full PAM stack.

The serial getty follows the same pattern on `ttyS0`.

---

## 3. runit

`/usr/sbin/runit` runs three shell stages:

| Stage | File | Work |
| --- | --- | --- |
| 1 | `/etc/runit/1` | mounts, `/run`/`/tmp`, hostname, sysctls, machine-id, random seed, `mdev -s`, hotplug helper |
| 2 | `/etc/runit/2` | `exec runsvdir -P /var/service` |
| 3 | `/etc/runit/3` | force-stops services, saves a random seed, syncs |

Services are plain `runsv` directories in `/etc/sv`, linked into `/var/service`:

| Service | Behaviour |
| --- | --- |
| `agetty-tty1`, `agetty-tty2` | local consoles |
| `agetty-ttyS0` | serial console |
| `network` | waits for a non-loopback interface, then `dhcpcd --nobackground --waitip=4 --timeout=30` |
| `firewall` | loads `/etc/nftables.conf` with `nft -f`, then sleeps |
| `syslog` | `busybox syslogd -n -O /var/log/messages` |
| `local` | mounts the ESP if `/etc/fstab` lists `/boot/efi`, runs `swapon -a`, then sleeps |

There is no udev. `devtmpfs` creates device nodes and `mdev` applies
`/etc/mdev.conf` for hotplug.

---

## 4. Installed system

`build/make-install-initramfs.sh` builds a separate, small initramfs containing
busybox, `e2fsck` and `init/install-init`. The kernel has ext4, virtio, AHCI,
NVMe and devtmpfs built in, so no storage modules are needed to find the root.

`init/install-init`:

1. mounts `proc`, `sys`, `devtmpfs`, `devpts`, `shm`, `/run`;
2. reads `root=` from `/proc/cmdline`;
3. resolves `UUID=`/`LABEL=` with `findfs`;
4. runs `e2fsck -p` (only exit codes 0 and 1 are acceptable);
5. mounts the root read-write;
6. moves the virtual filesystems and `exec switch_root /newroot /sbin/init`.

The installer writes the kernel and this initramfs into the ESP:

```text
/boot/efi/EFI/grintion/vmlinuz-grintion
/boot/efi/EFI/grintion/initramfs-install.img
/boot/efi/limine.conf
/boot/efi/limine-bios.sys
/boot/efi/EFI/BOOT/BOOTX64.EFI
```

The generated `/etc/fstab` references both partitions by UUID. The ESP is
mounted at `/boot/efi` with `umask=0077`; the ext4 root uses
`defaults,noatime`.

The disk layout is fixed:

```text
GPT
  p1  1 MiB .. 513 MiB   FAT32, LABEL=GRINTIONESP, ESP flag
  p2  513 MiB .. 100%    ext4,  LABEL=GRINTION_ROOT
```

There is no swap partition and no LVM. `local` runs `swapon -a`, so a user can
add a swap file or partition manually.

---

## 5. Installer internals

`bin/grintion-install` is intentionally a single shell script with explicit
steps rather than a Python framework:

1. argument parsing and a root/live-image check;
2. tool presence check (`parted`, `partprobe`, `mkfs.vfat`, `mkfs.ext4`,
   `blkid`, `rsync`, `openssl`, `python3`);
3. disk size check (4 GiB minimum), `parted` GPT creation, `partprobe`;
4. `mkfs.vfat -F32 -n GRINTIONESP`, `mkfs.ext4 -L GRINTION_ROOT -m 0`;
5. mount the root and ESP, `rsync` the live root (excluding `/proc`, `/sys`,
   `/dev`, `/run`, `/tmp`, `/mnt`, `/media`, `/lost+found`);
6. write `machine-id`, hostname, hosts and fstab;
7. create the user directly in `passwd`/`group`/`shadow`/`gshadow` with an
   `openssl passwd -6` hash. This avoids relying on `useradd` and PAM inside a
   minimal chroot;
8. copy the kernel, installed initramfs and Limine assets;
9. `limine bios-install` for BIOS; `efibootmgr` when running under UEFI;
10. `sync`, unmount everything, with a trap that unwinds on failure.

Account creation is deliberately data-driven: the installer edits the target
databases instead of running account tools in a chroot. The trade-off is that
the installer must keep the shadow field format correct, which the end-to-end
login test covers.

`--dry-run` stops after validation. `--force` allows running from an installed
system, which is useful for testing but not a supported upgrade path.

---

## 6. Package manager

`garb` is a single Python program. Its layout is filesystem-root relative so it
can manage the live overlay, an installed disk, or a test root:

```text
/etc/garb/repos.d/*.conf       repository name + url
/etc/garb/keys/<name>.pub      trusted Ed25519 public key
/var/cache/garb/repos/<name>/  verified index and downloaded archives
/var/lib/garb/db.json          installed package database
/var/lib/garb/tmp/             staging and rollback backups
```

An index is signed with Ed25519 over the exact `index.json` bytes. `garb update`
fetches `index.json` and `index.json.sig`, verifies with `openssl pkeyutl
-verify`, and only then stores and parses the index. Package archives are
verified against the index SHA-256 before extraction.

Installation is staged: extract into a temporary directory, verify every
declared file hash, check for undeclared files, then move files into place while
moving any existing files into a backup directory. A failure restores the
backup and removes files installed so far. The database is written atomically
with `os.replace`.

See [PACKAGE-MANAGER.md](PACKAGE-MANAGER.md) for the format and limits.

---

## 7. Security boundaries

| Boundary | Implementation |
| --- | --- |
| Boot chain | Limine loads an unsigned kernel and initramfs. **No Secure Boot, no signature, no measured boot.** |
| Kernel | BPF syscall, kexec, hibernation and `/dev/mem` are disabled at build time; io_uring is disabled at runtime by sysctl. |
| Runtime | sysctls in `/etc/sysctl.d/99-grintion.conf`, Yama ptrace scope 2, `dmesg_restrict`, `kptr_restrict=2`, protected links/FIFOs, `suid_dumpable=0`, core dumps to `/dev/null`. |
| Users | PAM with `pam_faillock`, root locked on installed systems unless a root password is set, `wheel` for sudo. |
| Network | `nftables` rules loaded at boot; DHCP client only, no listening services by default. |
| Storage | No encryption, no integrity measurement, no verified boot. The persistence partition is plain ext4. |

The live image intentionally grants passwordless root on the console. That is a
property of the medium, not of installed systems.

---

## 8. What is source-built and what is not

Built from pinned upstream sources by this repository:

- Linux 6.12.114;
- busybox 1.37.0 (static);
- runit 2.1.2;
- dhcpcd 10.5.2;
- bc 1.07.1 (build tool only).

Copied from the Arch build host and resolved into the image:

- glibc, bash, coreutils, util-linux, PAM, OpenSSL, OpenSSH client, Python,
  `iproute2`, `nftables`, `vim`, `less`, `tar`, `gzip`, `xz` and the rest of
  `config/rootfs.required-binaries`.

Vendored binaries:

- Limine 8.7.0 bootloader assets.

This split is the main architectural compromise of 1.0.0. See
[BUILDING.md](BUILDING.md) and the "What independent means" section in the
README.
