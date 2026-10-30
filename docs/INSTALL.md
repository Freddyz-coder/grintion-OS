# Installing Grintion-OS

Grintion-OS 1.0.0 installs from the live ISO to a single disk. The installer
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

- **Grintion-OS 1.0.0 (live, RAM)** - normal live boot.
- **Grintion-OS 1.0.0 (recovery shell)** - drops to `/bin/sh` before runit.

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
| `--force` | Allow running from a system that is not the live image. |

### After installation

Remove the installation medium and reboot. Log in as the user you created. Root
is locked by default, so administrative work goes through `sudo`.

```sh
sudo passwd root          # only if you want a root password
timedatectl               # UTC by default
ln -sf /usr/share/zoneinfo/Region/City /etc/localtime
```

To add packages, configure a repository first; the installed system ships no
enabled repository. See [PACKAGE-MANAGER.md](PACKAGE-MANAGER.md).

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

## Wi-Fi

The image contains `iw`, `wpa_supplicant` and `wpa_passphrase`, but no network
manager and no wireless DHCP service. For a quick manual connection:

```sh
ip link set wlan0 up
wpa_passphrase "SSID" "passphrase" > /etc/wpa_supplicant/wpa_supplicant.conf
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
dhcpcd wlan0
```

The `network` service only starts `dhcpcd` on wired interfaces. This is a known
limitation of 1.0.0, not a supported roaming setup.

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

**No network after install.** The `network` service runs `dhcpcd` on the first
wired interface. Check `sv status /var/service/network` and
`cat /var/log/messages`. Virtio and e1000 NICs are supported by the kernel
configuration.

**Serial console.** Both boot entries add `console=ttyS0,115200`. Add
`grintion.serial=1` to keep kernel messages on the serial port.
