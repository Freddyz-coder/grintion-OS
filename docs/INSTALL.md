# Installing Grintion-OS

Grintion-OS 0.7.0 installs from the live ISO to a single disk. The installer
repartitions the **entire** target disk: a 512 MiB EFI system partition and an
ext4 root partition. There is no dual-boot or custom-partition mode in this
release.

If you want to try the system without touching a disk, boot the ISO and stop at
the live shell. Nothing is written to storage in that mode.

---

## 1. Write the ISO to removable media

```sh
sudo dd if=output/grintion-os-x86_64.iso of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Replace `/dev/sdX` with the whole device, not a partition. The image is hybrid
and boots on BIOS and UEFI systems. Secure Boot must be disabled in firmware:
the Limine bootloader is not signed and there is no shim.

## 2. Boot the live environment

The boot menu offers two entries:

- **Grintion-OS 0.7.0 (live, RAM)** - normal live boot.
- **Grintion-OS 0.7.0 (recovery shell)** - drops to `/bin/sh` before runit.

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
2. create a GPT with a 512 MiB FAT32 ESP and an ext4 root;
3. mount the new root and copy the live filesystem with `rsync`;
4. create the user you specify, add it to `wheel`, and copy `/etc/skel`;
5. write `/etc/fstab`, `/etc/hostname`, the machine ID and the initramfs;
6. install Limine for BIOS or UEFI, whichever the live system booted with;
7. unmount everything, including on failure.

### Unattended

```sh
grintion-install --unattended --disk /dev/vda \
    --hostname box --user grintion --password 'change-me'
```

`--unattended` refuses to run without `--disk`, `--user` and `--password`.
Passwords on the command line are visible in the process list; use the
interactive prompt on a shared machine.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--dry-run` | Validate arguments, tools and the disk, then exit. |
| `--root-password PASS` | Set a root password. By default root is locked on the installed system; use `sudo` from the created user. |
| `--no-bootloader` | Skip Limine, for an externally managed boot setup. |
| `--swap-size MIB` | Add a linux-swap partition at the end of the disk (default: none). |
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

Grintion-OS boots into a lightweight console prompt for administrative efficiency, with complete support for installing graphical desktop environments:

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
  read the USB stick can read those files.
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
failing step: root argument, device resolution, `e2fsck` or mount. Check that
the disk is attached and that the firmware boot order points at it.

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
