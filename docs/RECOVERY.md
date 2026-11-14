# Recovery and rollback

Grintion-OS provides built-in recovery, rollback, and data resilience mechanisms
designed for non-systemd systems:
- Btrfs root snapshot management with writable boot entries and direct root rollback.
- Boot health monitoring with interactive session verification and automatic Limine auto-revert.
- Automated backup and restore with SHA-256 manifests.
- Factory reset and reinstall preserving user `/home`.
- Cross-release configuration and home migration bundles.
- Limine bootloader entry and password management.
- Read-only rescue recovery partition support.

---

## 1. Snapshots (Btrfs)

The installer creates `@` and `@snapshots` Btrfs subvolumes and mounts
`@snapshots` at `/.snapshots`. `grintion-snapshot` manages snapshots of `/`:

```sh
sudo grintion-snapshot create before-upgrade
sudo grintion-snapshot list
sudo grintion-snapshot list --json
sudo grintion-snapshot delete before-upgrade
```

A root snapshot does **not** include a separate `@home` subvolume or external
partitions. Keep important home data in backups (`grintion-backup`).

### Booting a Snapshot

To test or boot a previous snapshot:

```sh
sudo grintion-snapshot boot before-upgrade
```

This creates a writable copy under `@snapshots/<name>-boot-<timestamp>` and adds
a corresponding entry to `/boot/efi/limine.conf` (preserving a backup of the previous
configuration). Reboot and select the entry from the Limine menu.

### Direct Active Root Rollback

To replace the current running `@` subvolume with a chosen snapshot:

```sh
sudo grintion-snapshot rollback before-upgrade
```

The current `@` root subvolume is safely moved to `@broken-<timestamp>`, and the
target snapshot is restored as the active `@` subvolume. Reboot into the restored
system immediately.

`garb upgrade` automatically invokes `grintion-snapshot create pre-upgrade` prior
to executing package upgrades on Btrfs roots.

Rollback is explicit and reversible:

```sh
sudo grintion-snapshot rollback before-upgrade --dry-run
sudo grintion-snapshot rollback before-upgrade --yes
sudo grintion-snapshot prune --keep 5 --dry-run
sudo grintion-snapshot status --json
```

A rollback first creates a read-only `pre-rollback-<timestamp>` safety snapshot
(best effort on a full filesystem), moves the active `@` to `@broken-<timestamp>`,
and keeps only the three newest broken roots. `/home` is never touched.

### Self-healing

`grintion-selfheal` runs after `boot-health` and repairs tmp modes, a read-only
root, broken service links, stale locks, resolver state, loopback, unloaded
AppArmor policy, inactive zram and exited services. See
[SELF-HEALING.md](SELF-HEALING.md).

---

## 2. Boot Health Monitoring and Auto-Revert

The `boot-health` runit service (`/etc/sv/boot-health`) records boot attempts.
The boot is marked healthy when either:
1. An interactive or graphical session is confirmed via `grintion-boot-health verify-session`.
2. The system remains stable through the 60-second window.

### Status and Inspection

```sh
grintion-boot-health status
grintion-boot-health status --json
```

### Auto-Revert

If three consecutive boot attempts fail without reaching a healthy session,
`boot-health` writes `/var/lib/grintion/boot-health/failed` and invokes:

```sh
grintion-boot-health auto-revert
```

`auto-revert` inspects available snapshot boot entries and recovery entries in
`/boot/efi/limine.conf`, sets the default bootloader entry to the most recent
snapshot or recovery entry, and logs the reversion. The edit is written through
a validated temporary file with a `.pre-boot-health` backup. This changes only
the default boot entry: it does not restore files or prove that the alternate
entry boots on the current hardware. Use `grintion-snapshot rollback` for the
actual filesystem rollback.

---

## 3. Limine Bootloader Management (`grintion-boot`)

`grintion-boot` manages Limine boot entries, boot timeout, and bootloader password protection:

```sh
# List all configured boot entries (* denotes default)
sudo grintion-boot list
sudo grintion-boot list --json

# Set default boot entry
sudo grintion-boot set-default "Grintion-OS 0.14.3"

# Set boot menu timeout in seconds
sudo grintion-boot set-timeout 5

# Add a custom boot entry
sudo grintion-boot add --title "Custom Kernel" --kernel /vmlinuz-custom --cmdline "quiet"

# Remove a boot entry
sudo grintion-boot remove "Custom Kernel"

# Protect boot menu edits with a password
sudo grintion-boot set-password
```

---

## 4. Backups and Restore (`grintion-backup`)

`grintion-backup` creates compressed tar archives with SHA-256 manifests covering
system configs (`/etc`), installed package state, or user data:

```sh
# Create a system backup archive
sudo grintion-backup create

# Create backup of a specific directory (e.g. /home)
sudo grintion-backup create /home --name user-backup

# List existing backups and verify manifest integrity
sudo grintion-backup list
sudo grintion-backup list --json

# Verify archive integrity
sudo grintion-backup verify /var/backups/grintion/backup-20261107.tar.gz

# Restore a backup archive
sudo grintion-backup restore /var/backups/grintion/backup-20261107.tar.gz

# Schedule automated daily/weekly backups via runit
sudo grintion-backup schedule --frequency daily
```

---

## 5. Factory Reset (`grintion-reset`)

To reset the operating system to factory baseline while preserving user accounts
and `/home`:

```sh
# Inspect available reset points
sudo grintion-reset list-points

# Perform factory reset preserving /home
sudo grintion-reset factory-reset --keep-home

# Status of current reset capability
sudo grintion-reset status
```

---

## 6. System Migration (`grintion-migrate`)

`grintion-migrate` exports user accounts, home directories, network profiles, and
configuration files into a relocatable, cryptographically verified migration bundle:

```sh
# Export system and user configurations to a migration bundle
sudo grintion-migrate export /tmp/grintion-migration.tar.gz

# Verify migration bundle contents and SHA-256 manifest
sudo grintion-migrate verify /tmp/grintion-migration.tar.gz

# Import bundle on a freshly installed system
sudo grintion-migrate import /tmp/grintion-migration.tar.gz
```

---

## 7. Recovery Partition and Live Rescue

### Recovery Partition
When installed with `--recovery-partition` (e.g., `--recovery-size 2048`),
a dedicated read-only partition is created with a standalone recovery kernel and
initramfs. Selecting `Grintion-OS (Recovery Environment)` from the Limine menu
boots directly into an offline maintenance shell without requiring a USB stick.

### Manual Live ISO Rescue

From the live USB:

```sh
# If encrypted, unlock LUKS2 container:
sudo cryptsetup open /dev/vda2 grintion

# Mount root and ESP:
sudo mount /dev/mapper/grintion /mnt        # or /dev/vda2 if unencrypted
sudo mount /dev/vda1 /mnt/boot/efi

# Chroot into installed environment:
sudo grintion-chroot /mnt
```

Inside the chroot, `garb`, `pacman`, `limine-deploy`, and `grintion-boot` can
repair packages, restore snapshots, or re-install the bootloader.
