# Architecture

Grintion-OS is an x86_64 Linux operating system built around a source-built
Linux kernel, a runit userland, a read-only live root that can be overlaid
with RAM or persistent storage, and full support for graphical desktop
environments (XFCE, GNOME, KDE Plasma, Sway, LXQt, i3) via garb and grintion-desktop.
This document describes the moving parts and the reasoning behind them.

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

Both add `console=ttyS0,115200 console=tty0` so the display screen (`tty0`)
is the primary console with active keyboard input, while logs are also mirrored
to serial (`ttyS0`) for headless virtualization.

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
| `network` | applies `/etc/grintion/network.conf` (DHCP or static), or auto-detects wired interfaces for DHCP when no interface sections exist |
| `wpa_supplicant` | opt-in Wi-Fi association for the `[wifi]` section; enabled by `grintion-network connect` |
| `firewall` | loads `/etc/nftables.conf` with `nft -f`, then sleeps |
| `syslog` | `busybox syslogd -n -O /var/log/messages` |
| `seatd` | provides `/run/seatd.sock` for Wayland compositors without logind |
| `udev` | runs standalone `systemd-udevd`, not systemd, so libinput can enumerate devices |
| `local` | mounts the ESP if `/etc/fstab` lists `/boot/efi`, runs `swapon -a`, then sleeps |

`/etc/grintion/network.conf` is parsed by `etc/grintion/network.lib.sh`
(`network_conf_get`, `network_sections`). `grintion-network` edits that file
atomically and restarts the services; `grintion-network connect` links
`/etc/sv/wpa_supplicant` into `/var/service` and writes a mode-0600
`wpa_supplicant.conf` from the plaintext passphrase or 64-hex PSK.

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
  p3  optional end       linux-swap, LABEL=GRINTION_SWAP (--swap-size MIB)
```

The installer can create a swap partition; with `--encrypt` it is LUKS2 and
opened by `/etc/sv/cryptswap` from a root-only key. LVM is not implemented.
`local` also runs `swapon -a`, so a manually configured swap file or partition
still works.

---

## 5. Installer internals

`bin/grintion-install` is intentionally a single shell script with explicit
steps rather than a Python framework:

1. argument parsing, an answer-file pre-scan and a root/live-image check;
2. tool presence check (`parted`, `partprobe`, `mkfs.vfat`, `blkid`, `rsync`,
   `openssl`, `python3`, plus `mkfs.ext4`, or `mkfs.btrfs`/`btrfs` and
   `cryptsetup` when selected);
3. disk size check (4 GiB minimum), swap-size validation, an optional SMART
   health probe, `parted` GPT creation, `partprobe`, then partition discovery
   through `lsblk` rather than guessing the suffix from the device name;
4. `mkfs.vfat -F32 -n GRINTIONESP`; LUKS2 `luksFormat`/`luksOpen` when
   `--encrypt`; `mkfs.ext4` or Btrfs `mkfs` with `@`/`@snapshots`/`@home`
   subvolumes; `mkswap` for plain or LUKS2 swap;
5. mount the selected subvolume and ESP, `rsync` the live root (excluding
   `/proc`, `/sys`, `/dev`, `/run`, `/tmp`, `/mnt`, `/media`, `/lost+found`);
6. write `machine-id`, hostname, hosts, fstab and the encrypted-swap key;
7. create the user directly in `passwd`/`group`/`shadow`/`gshadow`, then set
   the password through the target's `chpasswd` (yescrypt per
   `/etc/login.defs`) with an `openssl passwd -6 -stdin` fallback. The secret
   never appears in an argument list;
8. copy the kernel, installed initramfs and Limine assets, with
   `cryptdevice=`, `rootflags=subvol=@` and the console order in the cmdline;
9. `limine bios-install` for BIOS; `efibootmgr` when running under UEFI;
10. run `grintion-verify-install`, `sync`, and unmount everything, with a trap
    that unwinds on failure and closes the LUKS mappings.

Account creation is deliberately data-driven: the installer edits the target
databases instead of running useradd in a chroot. Passwords are applied
separately with `chpasswd` inside the target, so the hash method follows
`/etc/login.defs`; the end-to-end login test covers both paths.

`--dry-run` stops after validation; with `--json` it prints the disk,
filesystem, subvolume and encryption plan. `--force` allows running from an
installed system, which is useful for testing but not a supported upgrade path.
The installed initramfs contains busybox, e2fsck, cryptsetup and the dynamic
library closure; `/init` resolves `cryptdevice=`, prompts on the configured
console, mounts `rootflags=` and only runs e2fsck for ext filesystems.

Desktop installs are data-driven: `grintion-desktop` reads
`/etc/grintion/desktops.d/<name>.conf` (`PACKAGES`, `DM`, `DM_BIN`, `XINITRC`,
`DISPLAY_SERVER`) and `/etc/grintion/drivers.conf` supplies the GPU package
matrix. `list --json` exposes the profiles and `uninstall <name>` reverses an
install; display-manager supervision uses the tracked
`/etc/sv/display-manager/run` script. For profiles whose `DISPLAY_SERVER`
contains `wayland`, `grintion-desktop` enables `seatd` and adds human users to
the `seat` group. `grintion-session` creates a private `XDG_RUNTIME_DIR`, starts
a session bus when needed, exports the session type and seat socket, and execs
the compositor. eudev/libinput and logind are still absent, so Wayland sessions
are **not** claimed as verified.

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

The image includes `pacman`; `apk` is not installed. `garb` can delegate
`install`, `remove`, `update`, `search`, `info`, `verify` and `upgrade` to
pacman instead of using this layout. Auto-detection is limited to `--root /`;
the signed-repository implementation remains available with `--backend native`.
The image ships `/etc/pacman.conf`, the Arch public keyring and a local package
database seeded from the build host by `build/seed-pacman-db.py`, so pacman
does not overwrite the curated glibc. `/etc/mtab` points at
`/proc/self/mounts`, so `CheckSpace` sees the overlay mounts and package
installation works. See [PACKAGE-MANAGER.md](PACKAGE-MANAGER.md).

An index is signed with Ed25519 over the exact `index.json` bytes. `garb update`
fetches `index.json` and `index.json.sig`, verifies with `openssl pkeyutl
-verify`, and only then stores and parses the index. The index carries a
monotonic `index_version` and an `expires` timestamp; expired or older-than-
cached indexes are refused, so a captured index cannot be replayed. Package
archives are verified against the index SHA-256 before extraction, and
setuid/setgid files are rejected.

Installation is staged: extract into a temporary directory, verify every
declared file hash, check for undeclared files, then move files into place while
moving any existing files into a backup directory. A declared path owned by
another package is refused unless `--force` is used. A failure restores the
backup and removes files installed so far; an incomplete restore keeps the
backup directory and reports it. The database is written atomically with
`os.replace`, fsynced, and the parent directory is fsynced as well. Removal
refuses to break a reverse dependency unless forced.

Mutating transactions hold an exclusive `flock` on `/var/lib/garb/lock`, append
durable `started`/`committed`/`rolled-back` records to
`/var/lib/garb/journal.jsonl`, and are inspectable with `garb history` and
`garb fsck`. A corrupt database is a hard error rather than an empty database,
because an empty database loses the file-ownership records removal depends on.

See [PACKAGE-MANAGER.md](PACKAGE-MANAGER.md) for the format and limits.

---

## 7. Security boundaries

| Boundary | Implementation |
| --- | --- |
| Boot chain | Live ISO boots via Limine. Installed systems support Unified Kernel Images (UKI) and Secure Boot with locally enrolled MOK keys (`grintion-secureboot`), plus TPM 2.0 PCR attestation (`grintion-attest`). |
| Kernel | BPF syscall, kexec, hibernation, binfmt_misc and `/dev/mem` are disabled at build time; io_uring is disabled at runtime by sysctl; only build-signed modules load. |
| Runtime | sysctls in `/etc/sysctl.d/99-grintion.conf`, Yama ptrace scope 2, `dmesg_restrict`, `kptr_restrict=2`, protected links/FIFOs, `suid_dumpable=0`, core dumps to `/dev/null`. AppArmor profiles enforce daemon isolation; Bubblewrap sandboxing (`grintion-sandbox`) isolates applications. |
| Users | PAM with `pam_faillock` and yescrypt; `su` and `sudo` restricted to `wheel`; root locked on installed systems unless a root password is set; auditd trails and sudo I/O logging active (`grintion-audit-log`). |
| Network | `nftables` rules loaded at boot; DHCP client only, no listening services by default; `grintion-network` manages roaming, enterprise 802.1X, and MAC randomization. |
| Packages | Native `garb` uses Ed25519-signed, expiring indexes, atomic generations, and rollback. The bundled `pacman` backend trusts the pinned Arch keyring with `SigLevel = Required DatabaseOptional` (Arch publishes no database signatures) and `/etc/mtab` tracking `/proc/self/mounts`. |
| Storage | Installed systems support LUKS2 full-disk root encryption, encrypted swap (`/etc/sv/cryptswap`), and encrypted `/home`. TPM sealing (`grintion-tpm-luks`) and file integrity checks (`grintion-integrity`) are built in. The live persistence partition remains plain ext4. |

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

This split is the main architectural compromise of 0.10.1. See
[BUILDING.md](BUILDING.md) and the "What independent means" section in the
README.
