# Installing Grintion-OS

Grintion-OS 0.10.0 installs from the live ISO to a target disk or existing
partitions. The installer supports automatic whole-disk partitioning or custom
pre-existing partitions (`--custom`), multi-filesystem roots (ext4, Btrfs, XFS,
F2FS), LUKS2 encryption for root and `/home`, swap partitions and root swapfiles,
dual-boot Limine chainloading, disk secure erase, removable/USB installs,
preservation of home data across reinstalls, and an interactive guided TUI
wizard (`--tui`).

If you want to try the system without touching a disk, boot the ISO and stop at
the live shell. Nothing is written to storage in that mode.

---

## 1. Write the ISO to removable media

```sh
sudo dd if=output/grintion-os-x86_64.iso of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Replace `/dev/sdX` with the whole device, not a partition. The image is hybrid
and boots on BIOS and UEFI systems. Secure Boot must be disabled in firmware to boot
the live installation media, as the live Limine bootloader does not carry a Microsoft-signed
shim. (After installation, user-owned Secure Boot can be enabled via MOK enrollment; see
[docs/SECURE-BOOT.md](SECURE-BOOT.md)).

## 2. Boot the live environment

The boot menu offers two entries:

- **Grintion-OS 0.10.0 (live, RAM)** - normal live boot.
- **Grintion-OS 0.10.0 (recovery shell)** - drops to `/bin/sh` before runit.

The live session logs in as `root` with no password. This is intentional for a
live medium: anyone with console access has root. Do not expose a live system to
untrusted people.

The root filesystem is an overlay: the initramfs is the read-only lower layer
and a tmpfs is the upper layer. Reboots discard all changes unless persistence
is configured (see below).

Check that the live system came up correctly:

```sh
uname -r                 # 6.12.114-grintion
ip addr show             # DHCP lease on the wired interface
sv status /var/service/* # every service should be "run"
```

## 3. Install

List candidate disks:

```sh
lsblk -d -o NAME,SIZE,MODEL,TYPE
```

Run the installer interactively:

```sh
grintion-install --disk /dev/vda
```

It will:

1. require an explicit confirmation that the disk will be erased;
2. create a GPT with a 512 MiB FAT32 ESP and the selected root filesystem
   (ext4 or Btrfs, optionally inside LUKS2);
3. mount the new root and copy the live filesystem with `rsync`;
4. create the user you specify, add it to `wheel`, and copy `/etc/skel`;
5. write `/etc/fstab`, `/etc/hostname`, the machine ID and the initramfs;
6. install Limine for BIOS or UEFI, whichever the live system booted with;
7. unmount everything, including on failure.

### Unattended

```sh
printf '%s\n' 'change-me' | grintion-install --unattended --disk /dev/vda \
    --hostname box --user grintion --password-stdin
```

`--unattended` refuses to run without `--disk`, `--user` and a password source:
`--password-stdin` or `GRINTION_USER_PASSWORD`. Passwords are deliberately not
accepted as command-line arguments because they are visible in the process list
and shell history. Add `--root-password-stdin` (or `GRINTION_ROOT_PASSWORD`) to
unlock root; otherwise root stays locked and administration goes through
`sudo`.

### Guided TUI Wizard

Launch the interactive guided terminal UI installer:

```sh
grintion-install --tui
```

The wizard walks through:
1. Target disk selection
2. Partitioning mode (Whole disk auto-partitioning or Custom pre-existing partitions)
3. Root filesystem (`ext4`, `btrfs`, `xfs`, `f2fs`)
4. Encryption (Root LUKS2 and optional dedicated encrypted `/home`)
5. Swap configuration (Swap partition or root swapfile)
6. Optional recovery partition
7. Desktop environment selection (`none`, `xfce`, `gnome`, `kde`, `sway`, `lxqt`, `i3`)
8. Hostname and user account credentials
9. Confirmation screen with automatic SMART health preflight and summary review

### Custom Partitioning

To install Grintion-OS into existing partitions without repartitioning the entire disk:

```sh
grintion-install --custom --root-part /dev/vda2 --esp-part /dev/vda1 \
    --swap-part /dev/vda3 --home-part /dev/vda4 \
    --hostname box --user grintion
```

### Encrypted and Multi-Filesystem Installs

```sh
printf '%s\n' 'user-secret' 'luks-secret' | grintion-install --unattended \
    --disk /dev/vda --hostname box --user grintion \
    --password-stdin --encrypt --passphrase-stdin \
    --filesystem btrfs --separate-home --swap-size 2048
```

Supported root filesystems:
- `btrfs`: Subvolume layout (`@`, `@snapshots`, optional `@home`). Default for rollback snapshots.
- `ext4`: Mature journaling filesystem.
- `xfs`: High performance and scalability.
- `f2fs`: Flash-friendly filesystem for solid-state storage.

For dedicated `/home` on non-Btrfs filesystems or dedicated partitions:
```sh
grintion-install --disk /dev/vda --home-size 20480 --encrypt-home ...
```
With `--encrypt-home`, the home container is formatted with LUKS2 and unlocked automatically at boot using a secure keyfile stored on the encrypted root filesystem (`/etc/grintion/home.key`).

To reuse an existing `/home` partition without reformatting it:
```sh
grintion-install --custom --root-part /dev/vda2 --esp-part /dev/vda1 \
    --home-part /dev/vda4 --keep-home ...
```

### Swap Partition vs Swap File

- **Swap partition:** `--swap-size 2048` allocates a dedicated partition. With `--encrypt`, it is encrypted via `/etc/sv/cryptswap`.
- **Swap file on root:** `--swap-file 2048` allocates a swap file directly on the root filesystem. On Btrfs roots, the installer automatically applies `nodatacow` (`chattr +C`) to guarantee safe swap operations.

### Dual-Boot Detection

During installation, `grintion-install` automatically probes all partitions for existing operating systems (Windows Boot Manager, other Linux distributions). When found, corresponding chainload entries are generated in Limine configuration (`/boot/efi/limine.conf`), preserving boot access to existing systems.

### Removable / USB Install

To install to an external USB flash drive or portable hard drive:

```sh
grintion-install --disk /dev/sdb --removable ...
```

In removable mode, the installer deploys the UEFI fallback loader (`EFI/BOOT/BOOTX64.EFI`) directly to the EFI partition without invoking `efibootmgr` or modifying the host computer's NVRAM variables.

### Recovery Partition

```sh
grintion-install --disk /dev/vda --recovery-partition --recovery-size 2048 ...
```

Provisions a dedicated read-only recovery partition containing a rescue kernel and initramfs, accessible via a recovery boot menu entry in Limine.

### Dry-run and Answer Files

A plan can be inspected without touching the disk or supplying secrets:

```sh
grintion-install --dry-run --json --disk /dev/vda --hostname box \
    --user grintion --encrypt --filesystem btrfs --separate-home
```

The output conforms to schema 2, including partition geometries, mountpoints, encryption modes, and dual-boot chainload plans. Answer files can be saved and supplied with `--config <file>`.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--tui`, `--interactive` | Launch the interactive guided TUI installation wizard. |
| `--custom` | Custom partition mode (requires `--root-part` and `--esp-part`). |
| `--root-part DEV` | Target root partition for custom installation. |
| `--esp-part DEV` | Target EFI system partition for custom installation. |
| `--swap-part DEV` | Target swap partition for custom installation. |
| `--home-part DEV` | Target `/home` partition for custom installation. |
| `--home-size MIB` | Allocate a separate `/home` partition (whole-disk mode). |
| `--encrypt-home` | Encrypt `/home` partition with LUKS2 keyfile at `/etc/grintion/home.key`. |
| `--keep-home` | Preserve existing `/home` directory contents across reinstallation. |
| `--swap-size MIB` | Add a swap partition at the end of the disk. Encrypted when `--encrypt` is set. |
| `--swap-file MIB` | Create a swap file on the root filesystem (nodatacow on Btrfs). |
| `--encrypt` | Encrypt the root partition with LUKS2 (aes-xts-plain64, argon2id). |
| `--passphrase-stdin` | Read the LUKS passphrase from standard input. |
| `--filesystem FS` | Choose root filesystem: `btrfs`, `ext4`, `xfs`, or `f2fs`. |
| `--separate-home` | Put `/home` on Btrfs `@home` subvolume (requires `--filesystem btrfs`). |
| `--secure-erase` | Securely erase the target disk with `blkdiscard` or zero-fill prior to partitioning. |
| `--removable`, `--usb` | Install in removable/USB mode without updating UEFI NVRAM entries. |
| `--recovery-partition` | Provision a dedicated rescue/recovery partition. |
| `--recovery-size MIB` | Size of recovery partition (default: 2048 MiB). |
| `--desktop ENV` | Pre-install a desktop environment (`xfce`, `gnome`, `kde`, `sway`, `lxqt`, `i3`). |
| `--dry-run` | Validate arguments, tools and the disk, then emit plan and exit. |
| `--json` | With `--dry-run`, print the partition plan as JSON (schema 2). |
| `--config FILE` | Read a JSON answer file. Command-line flags override its values. |
| `--root-password-stdin` | Read a root password from standard input. |
| `--skip-smart` | Skip the SMART health preflight. |
| `--skip-self-test` | Skip `grintion-verify-install` after copying. |
| `--serial` | Configure serial console on `ttyS0` for LUKS passphrase prompt. |
| `--no-bootloader` | Skip Limine installation for custom bootloader management. |
| `--force` | Allow running from a system that is not the live image. |

### After installation

Remove the installation medium and reboot. Log in as the user you created. Root
is locked by default, so administrative work goes through `sudo`.

```sh
sudo passwd root          # only if you want a root password
date                      # UTC by default
# The full timezone database is installed, so this works for any Region/City.
ln -sf /usr/share/zoneinfo/Region/City /etc/localtime
```

### Installing additional packages

The image includes **pacman** as an external backend for `garb`; `apk` is not
installed. After the network is up:

```sh
garb update
# or: garb --backend pacman update
garb install PACKAGE
```

`garb update` synchronizes the Arch `core` and `extra` databases. `garb install`
delegates to `pacman -S --noconfirm`. The native signed-repository backend is
still available with `garb --backend native`; it does not use pacman.

Package installation works out-of-the-box using the bundled pacman backend
and `/etc/mtab` tracking kernel mounts:

```sh
garb update
garb install jq
```

`garb list` and `garb clean` operate on the native signed-repository database
and cache; use `pacman -Q` / `pacman -Sc` for pacman-installed packages.

---

## Graphical Desktop Environments

Grintion-OS boots into a lightweight console prompt for administrative efficiency. Graphical desktop environments can be installed from this console. XFCE and i3 are verified in QEMU/KVM with keyboard and pointer input and working PipeWire audio; KDE Plasma, GNOME, LXQt and Sway remain unverified in 0.10.0 (see [VERIFICATION.md](VERIFICATION.md)).

### Pre-installing during disk installation

```sh
grintion-install --disk /dev/vda --user myuser --desktop xfce
```

### Installing on an active system

```sh
grintion-desktop list              # List supported environments
grintion-desktop install xfce      # Install XFCE desktop & LightDM
grintion-desktop install gnome     # Install GNOME desktop & GDM
grintion-desktop install kde       # Install KDE Plasma & SDDM
grintion-desktop install sway      # Install Sway Wayland tiling WM
grintion-desktop drivers           # Auto-detect GPU and install drivers
```

See [docs/DESKTOP-GUI.md](DESKTOP-GUI.md) for detailed configuration, display manager supervision with runit, and hardware acceleration guides.

---

## Persistent live storage

Persistence keeps changes to the live root across reboots. The live init looks
for a filesystem labelled `GRINTION_PERSIST`, mounts it read-write, and uses
`upper/` and `work/` inside it as the overlay upper layer.

1. Boot the live image.
2. Create a partition on the live USB. It can be any size; 4 GiB is a practical
   minimum, and it must not overlap the ISO9660 data.
3. Format it:

   ```sh
   grintion-persist
   ```

   The tool lists block devices, asks for a partition, requires you to type
   `YES`, formats it ext4 with the right label and creates the overlay
   directories.

4. Reboot. The live init prints `persistence enabled on ...`.

Things to know:

- The persistence partition stores the **entire** upper layer, including
  passwords, SSH keys and package state. It is not encrypted. Anyone who can
  read the USB stick can read those files. The live init mounts it
  `nosuid,nodev` so it cannot inject setuid binaries or device nodes.
- A full partition makes the overlay fail; the live init falls back to RAM only
  if the mount itself fails, not when the filesystem fills later.
- To reset persistence, reformat the partition or delete `upper/` and `work/`
  while it is unmounted.
- The installer does **not** create a persistence partition and installed
  systems do not use one.

---

## Networking

The `network` service reads `/etc/grintion/network.conf`. With no explicit
`[interface ...]` sections it runs DHCP on every detected wired interface.
Configure static addressing with:

```sh
grintion-network set-static enp0s3 192.168.1.50/24 192.168.1.1 1.1.1.1,8.8.8.8
```

`grintion-network status` shows the configuration, current addresses and service
state. `grintion-network apply` restarts the supervised services after manual
configuration edits.

### Wi-Fi

`grintion-network connect` writes the `[wifi]` section, enables the supervised
`wpa_supplicant` service and restarts networking:

```sh
grintion-network connect "SSID"
grintion-network connect "SSID" "passphrase"   # non-interactive
grintion-network status
grintion-network disconnect
```

The passphrase is stored in `/etc/grintion/network.conf` with mode `0600`; the
generated `wpa_supplicant.conf` is also `0600`. A 64-hex PSK is accepted without
quotes. `grintion-network wifi-scan` lists visible SSIDs.

The manual tools (`iw`, `wpa_supplicant`, `wpa_cli`, `rfkill`) remain available
for debugging, but the supervised service is the supported path.

---

## Troubleshooting

**The installer refuses the disk.** It requires a block device, at least 4 GiB
of space, and no mounted partitions. Unmount anything auto-mounted by the live
session and retry.

**The installed system drops to a recovery shell.** The message names the
failing step: root argument, LUKS unlock, filesystem check or mount. Check that
the disk is attached and that the firmware boot order points at it. For an
encrypted install, the prompt is on the last console listed on the kernel
command line; use `--serial` if the display is not available. See
[RECOVERY.md](RECOVERY.md) for snapshot, boot-health and self-test commands.

**UEFI boot does not appear.** Confirm the firmware is in UEFI mode (not CSM),
Secure Boot is off, and the ESP contains `EFI/BOOT/BOOTX64.EFI`. The installer
installs Limine to the removable-media path, so no NVRAM entry is required.

**No network after install.** Check `grintion-network status`, then
`sv status /var/service/network` and `cat /var/log/dhcpcd.log`. The service
honours `/etc/grintion/network.conf`; with no interface sections it runs DHCP on
every detected wired interface. Virtio and e1000 NICs are supported by the
kernel configuration.

**Virtual Machine Requirements (VirtualBox / QEMU / VMware):**
- **RAM:** Minimum **2048 MB (2 GB)** recommended for the live environment. Because Grintion-OS runs from a high-speed memory overlay (unpacking the live root filesystem into RAM), virtual machines configured with under 1024 MB RAM will encounter an out-of-memory error during initramfs decompression (`Initramfs unpacking failed: write error`).
- **CPUs:** 2 vCPUs recommended.
- **Graphics Controller:** VMSVGA (VirtualBox) or VirtIO GPU (QEMU).

**Serial console.** Both boot entries add `console=ttyS0,115200 console=tty0` so the display screen (`tty0`) is the primary active console while maintaining serial output mirroring (`ttyS0`).
